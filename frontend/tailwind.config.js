/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
  // Naive UI 自带 reset，关闭 tailwind preflight 避免冲突
  corePlugins: {
    preflight: false,
  },
}
