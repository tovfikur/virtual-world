/**
 * Parcel Validation Utility
 * Validates that selected lands form a connected parcel
 */

/**
 * Validate that all lands are edge-connected (form a single contiguous parcel).
 *
 * Uses BFS flood-fill algorithm to verify connectivity.
 * Only 4-directional adjacency is considered (no diagonals).
 *
 * @param {Array} lands - Array of land objects with x, y coordinates
 * @returns {Object} - { valid: boolean, error: string|null }
 */
export function validateConnectivity(lands) {
  if (!lands || lands.length === 0) {
    return { valid: false, error: "No lands selected" };
  }

  if (lands.length === 1) {
    return { valid: true, error: null };  // Single land is always connected
  }

  // Create set of coordinates for O(1) lookup
  const coordSet = new Set(lands.map(l => `${l.x}_${l.y}`));
  const visited = new Set();
  const queue = [`${lands[0].x}_${lands[0].y}`]; // Start BFS from first land

  // BFS flood-fill
  while (queue.length > 0) {
    const coord = queue.shift();

    if (visited.has(coord)) {
      continue;
    }

    visited.add(coord);

    // Parse coordinates
    const [x, y] = coord.split('_').map(Number);

    // Check 4-directional neighbors (no diagonals)
    const neighbors = [
      [x, y + 1],   // North
      [x, y - 1],   // South
      [x + 1, y],   // East
      [x - 1, y],   // West
    ];

    for (const [nx, ny] of neighbors) {
      const neighborCoord = `${nx}_${ny}`;
      if (coordSet.has(neighborCoord) && !visited.has(neighborCoord)) {
        queue.push(neighborCoord);
      }
    }
  }

  // All lands should be reachable from the starting point
  if (visited.size !== lands.length) {
    return {
      valid: false,
      error: `Lands must be connected (edge-adjacent). Found ${visited.size}/${lands.length} connected lands.`
    };
  }

  return { valid: true, error: null };
}

/**
 * Calculate the bounding box for a parcel.
 *
 * @param {Array} lands - Array of land objects with x, y coordinates
 * @returns {Object} - { min_x, max_x, min_y, max_y }
 */
export function calculateBoundingBox(lands) {
  if (!lands || lands.length === 0) {
    return { min_x: 0, max_x: 0, min_y: 0, max_y: 0 };
  }

  const xCoords = lands.map(l => l.x);
  const yCoords = lands.map(l => l.y);

  return {
    min_x: Math.min(...xCoords),
    max_x: Math.max(...xCoords),
    min_y: Math.min(...yCoords),
    max_y: Math.max(...yCoords)
  };
}

/**
 * Calculate the center point (centroid) of a parcel.
 *
 * @param {Array} lands - Array of land objects with x, y coordinates
 * @returns {Object} - { x: number, y: number }
 */
export function calculateCenterPoint(lands) {
  if (!lands || lands.length === 0) {
    return { x: 0, y: 0 };
  }

  const totalX = lands.reduce((sum, l) => sum + l.x, 0);
  const totalY = lands.reduce((sum, l) => sum + l.y, 0);

  return {
    x: totalX / lands.length,
    y: totalY / lands.length
  };
}

/**
 * Group biomes in a parcel and count occurrences.
 *
 * @param {Array} lands - Array of land objects with biome property
 * @returns {Object} - { biome_name: count }
 */
export function groupBiomes(lands) {
  if (!lands || lands.length === 0) {
    return {};
  }

  return lands.reduce((acc, land) => {
    const biome = land.biome || 'unknown';
    acc[biome] = (acc[biome] || 0) + 1;
    return acc;
  }, {});
}
