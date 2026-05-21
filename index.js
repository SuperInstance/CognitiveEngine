/**
 * @superinstance/luciddreamer
 *
 * Maritime intelligence system — distills cloud AI into compiled edge tiles.
 *
 * This is the Node.js shim for the LucidDreamer package.
 * The core runtime is Python-based. This module provides metadata
 * and a bridge for JS consumers to discover and invoke the Python toolchain.
 */

"use strict";

const path = require("path");

const pkg = require("./package.json");

module.exports = {
  /** Package metadata */
  name: pkg.name,
  version: pkg.version,
  description: pkg.description,

  /** Absolute path to the Python package root */
  pythonRoot: path.resolve(__dirname, "luciddreamer"),

  /** Path to the mesh module */
  meshPath: path.resolve(__dirname, "luciddreamer", "mesh.py"),

  /** Path to the compiler module */
  compilerPath: path.resolve(__dirname, "luciddreamer", "compiler.py"),

  /** Path to the router module */
  routerPath: path.resolve(__dirname, "luciddreamer", "router.py"),

  /**
   * Run a LucidDreamer CLI command via Python.
   * @param {string[]} args - Arguments to pass to luciddreamer CLI
   * @returns {Promise<{stdout: string, stderr: string}>}
   */
  run(args = []) {
    const { execFile } = require("child_process");
    const script = path.join(this.pythonRoot, "cli.py");
    return new Promise((resolve, reject) => {
      execFile("python3", [script, ...args], (error, stdout, stderr) => {
        if (error) return reject(error);
        resolve({ stdout, stderr });
      });
    });
  },
};
