import gdstk
import os
import random

# Sky130: met5 drawing (71/20) and PR boundary (235/4)
METAL_LAYER = 71
METAL_DATATYPE = 20
PR_BOUNDARY_LAYER = 235
PR_BOUNDARY_DATATYPE = 4

MIN_METAL_WIDTH = 1.7
GAP = MIN_METAL_WIDTH  # spacing between rectangles
MIN_RECT_SIZE = MIN_METAL_WIDTH * 2

CANVAS_W = 140.0
CANVAS_H = 90.0

CELL_NAME = "my_logo"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "macros")

random.seed(int(os.environ.get("MACRO_SEED", "42")))


def inset_rect(x, y, w, h):
    """Shrink region by GAP on each side for DRC-clean metal."""
    if w <= 2 * GAP or h <= 2 * GAP:
        return None
    return (x + GAP, y + GAP, x + w - GAP, y + h - GAP)


def subtract_region(region, occupant, gap):
    """Split free region around occupant (x, y, w, h) leaving gap clearance."""
    x, y, w, h = region
    ox, oy, ow, oh = occupant
    ex0, ey0 = ox - gap, oy - gap
    ex1, ey1 = ox + ow + gap, oy + oh + gap

    leftover = []
    if ey1 < y + h:
        leftover.append((x, ey1, w, y + h - ey1))
    if ey0 > y:
        leftover.append((x, y, w, ey0 - y))

    mid_y0 = max(y, ey0)
    mid_y1 = min(y + h, ey1)
    mid_h = mid_y1 - mid_y0
    if mid_h > 0:
        if ex0 > x:
            leftover.append((x, mid_y0, ex0 - x, mid_h))
        if ex1 < x + w:
            leftover.append((ex1, mid_y0, x + w - ex1, mid_h))

    return [
        r for r in leftover
        if r[2] >= MIN_RECT_SIZE + 2 * GAP and r[3] >= MIN_RECT_SIZE + 2 * GAP
    ]


def region_area(region):
    return region[2] * region[3]


def place_big_rectangles(free_regions, rects, count_range=(3, 6)):
    """Place a few large rectangles into the largest available gaps."""
    num_big = random.randint(*count_range)
    for _ in range(num_big):
        if not free_regions:
            break
        free_regions.sort(key=region_area, reverse=True)
        x, y, w, h = free_regions.pop(0)

        max_rw = w * random.uniform(0.55, 0.88)
        max_rh = h * random.uniform(0.55, 0.88)
        if max_rw < MIN_RECT_SIZE + 2 * GAP or max_rh < MIN_RECT_SIZE + 2 * GAP:
            free_regions.append((x, y, w, h))
            continue

        rw = random.uniform(MIN_RECT_SIZE + 2 * GAP, max_rw)
        rh = random.uniform(MIN_RECT_SIZE + 2 * GAP, max_rh)
        rx = x + random.uniform(0, w - rw)
        ry = y + random.uniform(0, h - rh)

        metal = inset_rect(rx, ry, rw, rh)
        if metal:
            rects.append(metal)

        free_regions.extend(subtract_region((x, y, w, h), (rx, ry, rw, rh), GAP))


def subdivide_region(region, rects, depth=0, max_depth=10):
    """Recursively split remaining space into smaller and smaller rectangles."""
    x, y, w, h = region
    min_dim = min(w, h)

    if min_dim < MIN_RECT_SIZE + 2 * GAP:
        return

    if depth >= max_depth or min_dim < 8:
        metal = inset_rect(x, y, w, h)
        if metal:
            rects.append(metal)
        return

    # More likely to stop splitting as regions get smaller
    stop_chance = 0.15 + depth * 0.07
    if random.random() < stop_chance:
        metal = inset_rect(x, y, w, h)
        if metal:
            rects.append(metal)
        return

    split_vert = w >= h and w >= 2 * (MIN_RECT_SIZE + 2 * GAP) + GAP
    split_horiz = h > w and h >= 2 * (MIN_RECT_SIZE + 2 * GAP) + GAP
    if not split_vert and not split_horiz:
        if w >= 2 * (MIN_RECT_SIZE + 2 * GAP) + GAP:
            split_vert = True
        elif h >= 2 * (MIN_RECT_SIZE + 2 * GAP) + GAP:
            split_horiz = True
        else:
            metal = inset_rect(x, y, w, h)
            if metal:
                rects.append(metal)
            return

    if split_vert:
        frac = random.uniform(0.32, 0.68)
        split_x = x + frac * w
        left = (x, y, split_x - x - GAP / 2, h)
        right = (split_x + GAP / 2, y, x + w - split_x - GAP / 2, h)
        for child in (left, right):
            if child[2] >= MIN_RECT_SIZE + 2 * GAP and child[3] >= MIN_RECT_SIZE + 2 * GAP:
                subdivide_region(child, rects, depth + 1, max_depth)
    else:
        frac = random.uniform(0.32, 0.68)
        split_y = y + frac * h
        bottom = (x, y, w, split_y - y - GAP / 2)
        top = (x, split_y + GAP / 2, w, y + h - split_y - GAP / 2)
        for child in (bottom, top):
            if child[2] >= MIN_RECT_SIZE + 2 * GAP and child[3] >= MIN_RECT_SIZE + 2 * GAP:
                subdivide_region(child, rects, depth + 1, max_depth)


def generate_rectangles():
    rects = []
    free = [(0.0, 0.0, CANVAS_W, CANVAS_H)]

    place_big_rectangles(free, rects)
    free.sort(key=region_area, reverse=True)
    for region in free:
        subdivide_region(region, rects)

    return rects


def write_lef_file(filename, cell_name, width, height):
    with open(filename, "w") as f:
        f.write(f"# LEF file generated for {cell_name}\n")
        f.write("VERSION 5.8 ;\n")
        f.write("NAMESCASESENSITIVE ON ;\n")
        f.write("DIVIDERCHAR \"/\" ;\n")
        f.write("BUSBITCHARS \"[]\" ;\n")
        f.write("UNITS\n")
        f.write("   DATABASE MICRONS 1000 ;\n")
        f.write("END UNITS\n\n")
        f.write(f"MACRO {cell_name}\n")
        f.write("   CLASS BLOCK ;\n")
        f.write(f"   FOREIGN {cell_name} 0 0 ;\n")
        f.write(f"   SIZE {width:.3f} BY {height:.3f} ;\n")
        f.write("   SYMMETRY X Y ;\n")
        f.write(f"END {cell_name}\n")


def main():
    rects = generate_rectangles()
    lib = gdstk.Library()
    cell = lib.new_cell(CELL_NAME)

    for x0, y0, x1, y1 in rects:
        cell.add(
            gdstk.rectangle(
                (x0, y0),
                (x1, y1),
                layer=METAL_LAYER,
                datatype=METAL_DATATYPE,
            )
        )

    cell.add(
        gdstk.rectangle(
            (0, 0),
            (CANVAS_W, CANVAS_H),
            layer=PR_BOUNDARY_LAYER,
            datatype=PR_BOUNDARY_DATATYPE,
        )
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gds_path = os.path.join(OUTPUT_DIR, f"{CELL_NAME}.gds")
    lef_path = os.path.join(OUTPUT_DIR, f"{CELL_NAME}.lef")
    svg_path = os.path.join(OUTPUT_DIR, f"{CELL_NAME}.svg")

    write_lef_file(lef_path, CELL_NAME, CANVAS_W, CANVAS_H)
    lib.write_gds(gds_path)
    cell.write_svg(svg_path)
    print(f"Wrote {len(rects)} metal rects to {gds_path} ({CANVAS_W}x{CANVAS_H} µm)")


if __name__ == "__main__":
    main()
