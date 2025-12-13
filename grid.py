ROWS = 8
COLS = 25

def grid_to_pixel(row, col):
    """
    row: 0 = bottom, 7 = top
    col: 0 = left, 24 = right
    returns: (strand, index)
    """

    if row < 4:
        strand = 0
        local_row = row
    else:
        strand = 1
        local_row = row - 4

    if local_row % 2 == 0:
        # right → left
        index = local_row * COLS + (COLS - 1 - col)
    else:
        # left → right
        index = local_row * COLS + col

    return strand, index
