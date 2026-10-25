/** Nirikshan tokens: a government noting sheet, blue-black ink, red-ink remarks. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F4F6F1',      // noting-sheet paper
        sheet: '#FFFFFF',
        rule: '#D6DCD2',       // ruled lines
        ruleDark: '#B9C2B4',
        ink: { DEFAULT: '#1B2340', soft: '#4A5270', faint: '#7C8396' }, // blue-black ink
        royal: { DEFAULT: '#2C3E9E', dark: '#1F2D7A', wash: '#E8EBF8' }, // royal-blue fountain ink
        remark: { DEFAULT: '#B3261E', wash: '#FBE9E7' },   // red-ink remark: fraud signals
        defic: { DEFAULT: '#9A5600', wash: '#FBF0DC' },    // deficiencies
        review: { DEFAULT: '#2F5E8C', wash: '#E7EFF7' },   // needs review
        ok: { DEFAULT: '#2E6B3F', wash: '#E4F2E8' },       // verified
        manila: '#E9DDBF',                                  // file cover
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"IBM Plex Sans Devanagari"', 'system-ui', 'sans-serif'],
        cond: ['"IBM Plex Sans Condensed"', '"IBM Plex Sans"', 'sans-serif'],
        deva: ['"IBM Plex Sans Devanagari"', '"IBM Plex Sans"', 'sans-serif'],
      },
      fontSize: { xxs: ['0.6875rem', '1rem'] },
    },
  },
  plugins: [],
}
