// Pixel art shared by the 8-bit bubbles (SpeechBubble, VoiceTranscript).

const PIXEL_COLORS: Record<string, string> = { S: '#d5d5d5', K: '#000000', W: '#ffffff' }

// Bubble frame, 9-sliced by CSS border-image: 4x4 stepped corners, 1-pixel edges, white middle.
// S = light outer edge, K = black outline, W = white inside, . = transparent.
const FRAME = [
  '..SSSSS..',
  '.SKKKKKS.',
  'SKWWWWWKS',
  'SKWWWWWKS',
  'SKWWWWWKS',
  'SKWWWWWKS',
  'SKWWWWWKS',
  '.SKKKKKS.',
  '..SSSSS..',
]

export const pixelImage = (rows: string[]) => {
  const rects = rows.flatMap((row, y) =>
    [...row].flatMap((char, x) =>
      PIXEL_COLORS[char] ? [`<rect x="${x}" y="${y}" width="1" height="1" fill="${PIXEL_COLORS[char]}"/>`] : [],
    ),
  )
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${rows[0].length}" height="${rows.length}" ` +
    `shape-rendering="crispEdges">${rects.join('')}</svg>`
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`
}

export const FRAME_IMAGE = pixelImage(FRAME)
