import numpy as np
from scipy.spatial import cKDTree

def filt_pointcloud(coords):
    """
    Filter the point cloud to remove points that are too far to each other.
    This is done by using a KDTree to calculate the distance between points and their neighbors then remove points with large distances.
    """
    
    # Create a KDTree for efficient neighbor search
    tree = cKDTree(coords)

    # Query the tree for the nearest 10 neighbors
    distances, _ = tree.query(coords, k=11)

    # Get the mean distance to the 10 nearest neighbors (excluding the point itself)
    mean_10nn_dist = np.mean(distances[:, 1:], axis=1)

    # Calculate the mean and standard deviation of the mean distances
    mean_val = np.mean(mean_10nn_dist)
    std_val = np.std(mean_10nn_dist)

    # Define a threshold for filtering
    threshold = mean_val + 3 * std_val
    mask = mean_10nn_dist <= threshold

    return coords[mask]