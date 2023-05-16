ROOMantic is a Blender addon that enables you to model game levels using a doom-style sector-based approach. It is particularly useful for its ability to split rooms into separate objects, which is necessary to allow occlusion culling and avoid 'overdraw' on most game engines.

It is a re-written from scratch version of LevelBuddy.

## Features
- Per shape geometry separation (to avoid overdraw)
- Sector2D - similar to doom sector modeling allows you to pick floor/ceiling height as well as floor, wall, and ceiling materials
- Sector3D - similar to the 2D version, except it gives you all freedom for its shape
- Brush - the inverse of sectors, it adds geometry
- Auto texturing
- Some quality of life little tools:
    - 'Rip geometry' tool
    - 'Open image as material' tool

## Notes
- This addon is WIP
- I am working on a video tutorial (check the tips below for now)
- The addon is geared toward the creation of video game levels

## Tips
- If you ever created maps for classic Doom games, then this is going to be a walk in the park
- The basic setup consists of:
    - Toggle back face culling (helps to view things)
    - Toggle edge length (it helps a lot)
    - Toggle magnet snapping (set to increment)
- The shape types:
    - Sector2D are basically shapes with Solidify modifier
    - Sector3D allows you to model rooms in any shape
    - Brush is the inverse of a Sector - it 'adds' to room geometry
- Always try to keep rooms convex (good for rendering in-game and tools etc.)
    - Make use of the 'Rip' tooling for that
    - You can also manually split in edit mode with 'Alt -> M -> faces by edges' or 'Y', and then 'P -> by loose parts'