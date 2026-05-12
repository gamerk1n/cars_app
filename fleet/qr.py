from __future__ import annotations

VERSION = 4
SIZE = 21 + (VERSION - 1) * 4
DATA_CODEWORDS = 80
ECC_CODEWORDS = 20
FORMAT_ECL_LOW = 1


def qr_svg(data: str, *, scale: int = 8, border: int = 4) -> str:
    matrix = _make_qr_matrix(data.encode("utf-8"))
    width = (SIZE + border * 2) * scale
    cells = []
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            if value:
                cells.append(f"M{(x + border) * scale},{(y + border) * scale}h{scale}v{scale}h-{scale}z")
    path = " ".join(cells)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {width}" '
        f'width="{width}" height="{width}" role="img" aria-label="QR code">'
        '<rect width="100%" height="100%" fill="#fff"/>'
        f'<path d="{path}" fill="#000"/>'
        "</svg>"
    )


def _make_qr_matrix(data: bytes) -> list[list[bool]]:
    data_codewords = _encode_data(data)
    ecc = _reed_solomon_remainder(data_codewords, ECC_CODEWORDS)
    bits = _codewords_to_bits(data_codewords + ecc)

    base, is_function = _draw_function_patterns()
    best_matrix = None
    best_penalty = None
    for mask in range(8):
        matrix = [row[:] for row in base]
        _draw_data_bits(matrix, is_function, bits, mask)
        _draw_format_bits(matrix, is_function, mask)
        penalty = _penalty_score(matrix)
        if best_penalty is None or penalty < best_penalty:
            best_matrix = matrix
            best_penalty = penalty
    return best_matrix or base


def _encode_data(data: bytes) -> list[int]:
    if len(data) > DATA_CODEWORDS - 2:
        raise ValueError("QR data is too long for version 4-L byte mode.")

    bits = [0, 1, 0, 0]
    bits.extend(_int_to_bits(len(data), 8))
    for byte in data:
        bits.extend(_int_to_bits(byte, 8))

    capacity_bits = DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity_bits - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    codewords = [_bits_to_int(bits[i : i + 8]) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(codewords) < DATA_CODEWORDS:
        codewords.append(pad)
        pad = 0x11 if pad == 0xEC else 0xEC
    return codewords


def _draw_function_patterns() -> tuple[list[list[bool]], list[list[bool]]]:
    matrix = [[False] * SIZE for _ in range(SIZE)]
    is_function = [[False] * SIZE for _ in range(SIZE)]

    _draw_finder(matrix, is_function, 0, 0)
    _draw_finder(matrix, is_function, SIZE - 7, 0)
    _draw_finder(matrix, is_function, 0, SIZE - 7)
    _draw_alignment(matrix, is_function, 26, 26)

    for i in range(8, SIZE - 8):
        value = i % 2 == 0
        _set(matrix, is_function, i, 6, value)
        _set(matrix, is_function, 6, i, value)

    _set(matrix, is_function, 8, SIZE - 8, True)
    _reserve_format(is_function)
    return matrix, is_function


def _draw_finder(matrix, is_function, left: int, top: int) -> None:
    for y in range(-1, 8):
        for x in range(-1, 8):
            xx = left + x
            yy = top + y
            if not (0 <= xx < SIZE and 0 <= yy < SIZE):
                continue
            dark = (
                0 <= x <= 6
                and 0 <= y <= 6
                and (x in {0, 6} or y in {0, 6} or (2 <= x <= 4 and 2 <= y <= 4))
            )
            _set(matrix, is_function, xx, yy, dark)


def _draw_alignment(matrix, is_function, center_x: int, center_y: int) -> None:
    for y in range(-2, 3):
        for x in range(-2, 3):
            dark = max(abs(x), abs(y)) != 1
            _set(matrix, is_function, center_x + x, center_y + y, dark)


def _reserve_format(is_function) -> None:
    for i in range(9):
        if i != 6:
            is_function[8][i] = True
            is_function[i][8] = True
    for i in range(8):
        is_function[8][SIZE - 1 - i] = True
        is_function[SIZE - 1 - i][8] = True


def _draw_format_bits(matrix, is_function, mask: int) -> None:
    bits = _format_bits(mask)
    for i in range(6):
        _set(matrix, is_function, 8, i, _bit(bits, i))
    _set(matrix, is_function, 8, 7, _bit(bits, 6))
    _set(matrix, is_function, 8, 8, _bit(bits, 7))
    _set(matrix, is_function, 7, 8, _bit(bits, 8))
    for i in range(9, 15):
        _set(matrix, is_function, 14 - i, 8, _bit(bits, i))
    for i in range(8):
        _set(matrix, is_function, SIZE - 1 - i, 8, _bit(bits, i))
    for i in range(8, 15):
        _set(matrix, is_function, 8, SIZE - 15 + i, _bit(bits, i))
    _set(matrix, is_function, 8, SIZE - 8, True)


def _draw_data_bits(matrix, is_function, bits: list[bool], mask: int) -> None:
    bit_index = 0
    upward = True
    right = SIZE - 1
    while right > 0:
        if right == 6:
            right -= 1
        rows = range(SIZE - 1, -1, -1) if upward else range(SIZE)
        for y in rows:
            for x in [right, right - 1]:
                if is_function[y][x]:
                    continue
                value = bits[bit_index] if bit_index < len(bits) else False
                if _mask(mask, x, y):
                    value = not value
                matrix[y][x] = value
                bit_index += 1
        upward = not upward
        right -= 2


def _set(matrix, is_function, x: int, y: int, value: bool) -> None:
    matrix[y][x] = value
    is_function[y][x] = True


def _mask(mask: int, x: int, y: int) -> bool:
    return [
        (x + y) % 2 == 0,
        y % 2 == 0,
        x % 3 == 0,
        (x + y) % 3 == 0,
        (x // 3 + y // 2) % 2 == 0,
        (x * y) % 2 + (x * y) % 3 == 0,
        ((x * y) % 2 + (x * y) % 3) % 2 == 0,
        ((x + y) % 2 + (x * y) % 3) % 2 == 0,
    ][mask]


def _penalty_score(matrix: list[list[bool]]) -> int:
    score = 0
    for row in matrix:
        score += _run_penalty(row)
    for x in range(SIZE):
        score += _run_penalty([matrix[y][x] for y in range(SIZE)])
    for y in range(SIZE - 1):
        for x in range(SIZE - 1):
            value = matrix[y][x]
            if (
                matrix[y][x + 1] == value
                and matrix[y + 1][x] == value
                and matrix[y + 1][x + 1] == value
            ):
                score += 3
    score += _finder_penalty(matrix)
    dark = sum(1 for row in matrix for value in row if value)
    total = SIZE * SIZE
    score += abs(dark * 20 - total * 10) // total * 10
    return score


def _run_penalty(values: list[bool]) -> int:
    score = 0
    run_value = values[0]
    run_length = 1
    for value in values[1:]:
        if value == run_value:
            run_length += 1
            continue
        if run_length >= 5:
            score += run_length - 2
        run_value = value
        run_length = 1
    if run_length >= 5:
        score += run_length - 2
    return score


def _finder_penalty(matrix: list[list[bool]]) -> int:
    patterns = [
        [True, False, True, True, True, False, True, False, False, False, False],
        [False, False, False, False, True, False, True, True, True, False, True],
    ]
    score = 0
    for row in matrix:
        score += _pattern_count(row, patterns) * 40
    for x in range(SIZE):
        score += _pattern_count([matrix[y][x] for y in range(SIZE)], patterns) * 40
    return score


def _pattern_count(values: list[bool], patterns: list[list[bool]]) -> int:
    count = 0
    for i in range(len(values) - 10):
        window = values[i : i + 11]
        if any(window == pattern for pattern in patterns):
            count += 1
    return count


def _format_bits(mask: int) -> int:
    data = (FORMAT_ECL_LOW << 3) | mask
    rem = data << 10
    generator = 0x537
    for i in range(14, 9, -1):
        if (rem >> i) & 1:
            rem ^= generator << (i - 10)
    return ((data << 10) | rem) ^ 0x5412


def _reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    divisor = _reed_solomon_divisor(degree)
    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_multiply(coef, factor)
    return result


def _reed_solomon_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 2)
    return result


def _gf_multiply(x: int, y: int) -> int:
    result = 0
    while y:
        if y & 1:
            result ^= x
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
        y >>= 1
    return result & 0xFF


def _codewords_to_bits(codewords: list[int]) -> list[bool]:
    return [bool((byte >> i) & 1) for byte in codewords for i in range(7, -1, -1)]


def _int_to_bits(value: int, width: int) -> list[int]:
    return [(value >> i) & 1 for i in range(width - 1, -1, -1)]


def _bits_to_int(bits: list[int]) -> int:
    result = 0
    for bit in bits:
        result = (result << 1) | bit
    return result


def _bit(value: int, index: int) -> bool:
    return ((value >> index) & 1) != 0
