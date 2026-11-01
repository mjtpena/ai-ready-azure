// Course visual theme: "asphalt and lane-marking" — dark asphalt for openers and takeaways,
// white for working slides, amber as the single sharp accent, teal for data.
// The five AI-Ready Platform layers each own a colour (see docs/SCENARIO.md).
const THEME = {
  name: "AI-Ready Azure",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2933", // body text on light
    lt1: "FFFFFF", // light background
    dk2: "14191F", // asphalt — dark background
    lt2: "F2F4F7", // card tint on light
    accent1: "F5A623", // amber lane marking (sharp accent)
    accent2: "12A5A0", // teal (data)
    accent3: "52606D", // slate  (L1 Foundation)
    accent4: "7C5CFF", // violet (L4 Intelligence)
    accent5: "3DBE6B", // green  (L5 Experiences)
    accent6: "6B7785", // muted text
    hlink: "12A5A0",
    folHlink: "7C5CFF",
  },
};

// Layer palette by number (hex, used for shapes where a scheme colour is not available)
const LAYERS = {
  1: { name: "Foundation", hex: "52606D" },
  2: { name: "Trust and control", hex: "F5A623" },
  3: { name: "Data and context", hex: "12A5A0" },
  4: { name: "Intelligence", hex: "7C5CFF" },
  5: { name: "Experiences and agents", hex: "3DBE6B" },
};

const HEX = {
  text: "1F2933", muted: "6B7785", white: "FFFFFF", dark: "14191F", tint: "F2F4F7",
  amber: "F5A623", teal: "12A5A0", slate: "52606D", violet: "7C5CFF", green: "3DBE6B",
  line: "D5DAE1", red: "D64545", darkCard: "232B35",
};

module.exports = { THEME, LAYERS, HEX };
