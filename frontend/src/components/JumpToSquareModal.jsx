/**
 * JumpToSquareModal Component
 * Allows users to jump to a specific coordinate in the world
 */

import { useState } from "react";
import toast from "react-hot-toast";

function JumpToSquareModal({ onJump, onClose }) {
  const [x, setX] = useState("");
  const [y, setY] = useState("");
  const [z, setZ] = useState("0");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    const xNum = parseInt(x);
    const yNum = parseInt(y);
    const zNum = parseInt(z);

    // Validation
    if (isNaN(xNum) || isNaN(yNum) || isNaN(zNum)) {
      toast.error("Please enter valid numbers for coordinates");
      return;
    }

    // Coordinate bounds (typical world size)
    const MAX_COORD = 1000000;
    const MIN_COORD = -1000000;

    if (
      xNum < MIN_COORD ||
      xNum > MAX_COORD ||
      yNum < MIN_COORD ||
      yNum > MAX_COORD
    ) {
      toast.error(`Coordinates must be between ${MIN_COORD} and ${MAX_COORD}`);
      return;
    }

    if (zNum < 0 || zNum > 10) {
      toast.error("Zoom level must be between 0 and 10");
      return;
    }

    try {
      setIsLoading(true);
      await onJump({ x: xNum, y: yNum, z: zNum });
      toast.success(`Jumped to (${xNum}, ${yNum})`);
      onClose();
    } catch (error) {
      console.error("Jump failed:", error);
      toast.error("Failed to jump to coordinates");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold text-white">Jump to Square</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Info */}
          <p className="text-sm text-gray-400 mb-4">
            Enter the coordinates of the square you want to jump to
          </p>

          {/* X Coordinate */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              X Coordinate
            </label>
            <input
              type="number"
              value={x}
              onChange={(e) => setX(e.target.value)}
              placeholder="e.g., 0"
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
              required
              disabled={isLoading}
            />
          </div>

          {/* Y Coordinate */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Y Coordinate
            </label>
            <input
              type="number"
              value={y}
              onChange={(e) => setY(e.target.value)}
              placeholder="e.g., 0"
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
              required
              disabled={isLoading}
            />
          </div>

          {/* Zoom Level */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Zoom Level (0-10)
            </label>
            <input
              type="number"
              value={z}
              onChange={(e) => setZ(e.target.value)}
              min="0"
              max="10"
              step="0.5"
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
              disabled={isLoading}
            />
            <p className="text-xs text-gray-500 mt-1">Default is 1</p>
          </div>

          {/* Quick Navigation Examples */}
          <div className="bg-gray-700/50 rounded-lg p-3 mt-4">
            <p className="text-xs font-semibold text-gray-400 mb-2">
              Quick Jump:
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setX("0");
                  setY("0");
                  setZ("1");
                }}
                className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded transition-colors"
              >
                Origin (0, 0)
              </button>
              <button
                type="button"
                onClick={() => {
                  setX("100");
                  setY("100");
                  setZ("1");
                }}
                className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded transition-colors"
              >
                (100, 100)
              </button>
              <button
                type="button"
                onClick={() => {
                  setX("-100");
                  setY("-100");
                  setZ("1");
                }}
                className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded transition-colors"
              >
                (-100, -100)
              </button>
              <button
                type="button"
                onClick={() => {
                  setX("500");
                  setY("500");
                  setZ("1");
                }}
                className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-3 py-1.5 rounded transition-colors"
              >
                (500, 500)
              </button>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-4">
            <button
              type="submit"
              disabled={isLoading || !x || !y}
              className="flex-1 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
            >
              {isLoading ? "Jumping..." : "Jump"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default JumpToSquareModal;
