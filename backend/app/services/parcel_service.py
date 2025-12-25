"""
Parcel Service
Handles parcel validation and connectivity checks for marketplace
"""

from typing import List, Tuple, Dict, Set
import logging

logger = logging.getLogger(__name__)


class ParcelService:
    """Service for parcel validation and operations."""

    @staticmethod
    def validate_connectivity(land_coords: List[Tuple[int, int]]) -> bool:
        """
        Validate that all lands are edge-connected (form a single contiguous parcel).

        Uses BFS flood-fill algorithm to verify connectivity.
        Only 4-directional adjacency is considered (no diagonals).

        Args:
            land_coords: List of (x, y) coordinate tuples

        Returns:
            True if all lands form a single connected component, False otherwise

        Examples:
            >>> validate_connectivity([(0, 0), (1, 0), (1, 1)])  # L-shape
            True
            >>> validate_connectivity([(0, 0), (2, 0)])  # Gap in between
            False
            >>> validate_connectivity([(0, 0), (1, 1)])  # Diagonal only
            False
        """
        if not land_coords:
            logger.warning("Empty land_coords list provided")
            return False

        if len(land_coords) == 1:
            return True  # Single land is always connected

        # Convert to set for O(1) lookup
        coords_set: Set[Tuple[int, int]] = set(land_coords)
        visited: Set[Tuple[int, int]] = set()
        queue: List[Tuple[int, int]] = [land_coords[0]]  # Start BFS from first land

        # BFS flood-fill
        while queue:
            x, y = queue.pop(0)

            if (x, y) in visited:
                continue

            visited.add((x, y))

            # Check 4-directional neighbors (no diagonals)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (x + dx, y + dy)

                if neighbor in coords_set and neighbor not in visited:
                    queue.append(neighbor)

        # All lands should be reachable from the starting point
        is_connected = len(visited) == len(land_coords)

        if not is_connected:
            logger.warning(
                f"Parcel connectivity validation failed: "
                f"Visited {len(visited)}/{len(land_coords)} lands"
            )

        return is_connected

    @staticmethod
    def calculate_bounding_box(land_coords: List[Tuple[int, int]]) -> Dict[str, int]:
        """
        Calculate the bounding box for a parcel.

        Args:
            land_coords: List of (x, y) coordinate tuples

        Returns:
            Dictionary with min_x, max_x, min_y, max_y

        Example:
            >>> calculate_bounding_box([(5, 10), (6, 10), (5, 11)])
            {'min_x': 5, 'max_x': 6, 'min_y': 10, 'max_y': 11}
        """
        if not land_coords:
            return {"min_x": 0, "max_x": 0, "min_y": 0, "max_y": 0}

        x_coords = [x for x, y in land_coords]
        y_coords = [y for x, y in land_coords]

        return {
            "min_x": min(x_coords),
            "max_x": max(x_coords),
            "min_y": min(y_coords),
            "max_y": max(y_coords)
        }

    @staticmethod
    def calculate_center_point(land_coords: List[Tuple[int, int]]) -> Tuple[float, float]:
        """
        Calculate the center point (centroid) of a parcel.

        Args:
            land_coords: List of (x, y) coordinate tuples

        Returns:
            Tuple of (center_x, center_y) as floats

        Example:
            >>> calculate_center_point([(0, 0), (2, 0), (1, 2)])
            (1.0, 0.666...)
        """
        if not land_coords:
            return (0.0, 0.0)

        total_x = sum(x for x, y in land_coords)
        total_y = sum(y for x, y in land_coords)
        count = len(land_coords)

        return (total_x / count, total_y / count)


# Global instance
parcel_service = ParcelService()
