from typing import List

SIZE = 1024

def maximalRectangle(matrix: List[List[int]]) -> int:
    """
    Find the largest rectangle containing only 1s in a binary matrix.
    Returns the area of the rectangle and its coordinates (n1, n2, m1, m2),
    where n1 and n2 are the row indices and m1 and m2 are the column indices.
    """
    n, m = len(matrix), len(matrix[0])
    ans = 0
    heights = [0] * m
    n1 ,n2, m1, m2 = 0, 0, 0, 0
    for i in range(n-1, -1, -1):
        for j in range(m):
            if matrix[i][j] == 1:
                heights[j] += 1
            else:
                heights[j] = 0
        
        stack = []
        for j in range(m + 1):
            while stack and (j == m or heights[stack[-1]] > heights[j]):
                h = heights[stack.pop()]
                w = j if not stack else j - stack[-1] - 1
                if h * w > ans:
                    ans = h * w
                    n1 = i
                    n2 = i + h - 1
                    m1 = stack[-1] + 1 if stack else 0
                    m2 = j - 1
            stack.append(j)
    return n1, n2, m1, m2

def find_position(coords, height):
    """
    Find the camera position based on the point cloud coordinates and height.
    The position is determined to be above the center of the max empty sub matrix.
    """
    # Calculate the size of grid
    min = coords.min(axis=0)
    max = coords.max(axis=0)
    grid_x = (max[0] - min[0]) / SIZE
    grid_y = (max[1] - min[1]) / SIZE
    grid_z = (max[2] - min[2]) / SIZE

    # Calculate the z range
    z_1 = height - grid_z / 2
    z_2 = height + grid_z / 2

    # Create a matrix to represent the grid
    # 1 means empty, 0 means occupied
    # The matrix is initialized to 1, then set to 0 for occupied cells
    matrix = [[1 for _ in range(SIZE)] for _ in range(SIZE)]
    for coord in coords:
        if coord[2] < z_1 or coord[2] > z_2:
            continue
        x = int((coord[0] - min[0]) / grid_x)
        y = int((coord[1] - min[1]) / grid_y)
        matrix[x][y] = 0
    
    # Find the maximal rectangle in the matrix
    n1, n2, m1, m2 = maximalRectangle(matrix)

    # Calculate the camera position based on the maximal rectangle
    position_x = min[0] + (n1 + n2 + 1) / 2 * grid_x
    position_y = min[1] + (m1 + m2 + 1) / 2 * grid_y
    position_z = height

    return position_x, position_y, position_z