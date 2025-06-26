from typing import List

def maximalRectangle(self, matrix: List[List[str]]) -> int:
    n, m = len(matrix), len(matrix[0])
    ans = 0
    heights = [0] * m
    n1 ,n2, m1, m2 = 0, 0, 0, 0
    for i in range(n-1, -1, -1):
        for j in range(m):
            if matrix[i][j] == '1':
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
    return ans, (n1, n2, m1, m2)