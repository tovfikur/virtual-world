/**
 * Biome Color Utilities
 * Maps biome types to hex colors for rendering
 */

export const BIOME_COLORS = {
  ocean: 0x1e3a8a,      // Dark blue
  beach: 0xfbbf24,      // Sandy yellow
  plains: 0x84cc16,     // Light green
  forest: 0x15803d,     // Dark green
  desert: 0xfcd34d,     // Sandy yellow-orange
  mountain: 0x78716c,   // Gray
  snow: 0xf0f9ff,       // White-blue
};

export const BIOME_NAMES = {
  ocean: 'Ocean',
  beach: 'Beach',
  plains: 'Plains',
  forest: 'Forest',
  desert: 'Desert',
  mountain: 'Mountain',
  snow: 'Snow',
};

/**
 * Get hex color for a biome type
 * @param {string} biome - Biome name
 * @returns {number} Hex color value
 */
export function getBiomeColor(biome) {
  return BIOME_COLORS[biome?.toLowerCase()] || BIOME_COLORS.plains;
}

/**
 * Get display name for a biome
 * @param {string} biome - Biome name
 * @returns {string} Display name
 */
export function getBiomeName(biome) {
  return BIOME_NAMES[biome?.toLowerCase()] || 'Unknown';
}

/**
 * Get CSS color string for a biome
 * @param {string} biome - Biome name
 * @returns {string} CSS color string
 */
export function getBiomeColorCSS(biome) {
  const hex = getBiomeColor(biome);
  return `#${hex.toString(16).padStart(6, '0')}`;
}

/**
 * Get darker shade of biome color (for borders, etc.)
 * @param {string} biome - Biome name
 * @param {number} factor - Darkening factor (0-1)
 * @returns {number} Hex color value
 */
export function getBiomeColorDark(biome, factor = 0.7) {
  const color = getBiomeColor(biome);
  const r = Math.floor(((color >> 16) & 0xff) * factor);
  const g = Math.floor(((color >> 8) & 0xff) * factor);
  const b = Math.floor((color & 0xff) * factor);
  return (r << 16) | (g << 8) | b;
}

/**
 * Get biome rarity description
 * @param {string} biome - Biome name
 * @returns {string} Rarity level
 */
export function getBiomeRarity(biome) {
  const rarities = {
    ocean: 'Common',
    beach: 'Uncommon',
    plains: 'Common',
    forest: 'Common',
    desert: 'Uncommon',
    mountain: 'Rare',
    snow: 'Rare',
  };
  return rarities[biome?.toLowerCase()] || 'Unknown';
}
