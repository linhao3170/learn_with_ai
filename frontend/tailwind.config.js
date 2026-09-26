/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        'neon-blue': '#00d4ff',
        'neon-cyan': '#22d3ee',
        'neon-purple': '#a855f7',
        'neon-pink': '#ec4899',
        'neon-green': '#4ade80',
        'neon-amber': '#fbbf24',
        'deep-space': '#0a0a0f',
        'deep-surface': '#111118',
        'deep-card': '#16161f',
        'deep-border': '#1f1f2e',
        'deep-hover': '#1a1a28',
      },
      animation: {
        'glow-pulse': 'glow-pulse 3s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'scan': 'scan 4s linear infinite',
        'gradient-x': 'gradient-x 8s ease infinite',
        'fade-in-up': 'fade-in-up 0.6s ease-out forwards',
        'slide-in-left': 'slide-in-left 0.4s ease-out forwards',
        'slide-in-right': 'slide-in-right 0.4s ease-out forwards',
        'scale-in': 'scale-in 0.3s ease-out forwards',
        'shimmer': 'shimmer 2s linear infinite',
        // UI 重设计一轮新增：链式拉动 + 层进式展现
        // 链式拉动：左右两张核心卡各自被"拉"进画面（带轻微过冲），中间那根链子同时点亮
        'chain-pull-left': 'chain-pull-left 0.75s cubic-bezier(0.22, 1, 0.36, 1) both',
        'chain-pull-right': 'chain-pull-right 0.75s cubic-bezier(0.22, 1, 0.36, 1) both',
        // 链节脉冲：在链子上自左向右跑，表示"这一步通往下一步"
        'chain-travel': 'chain-travel 2.6s cubic-bezier(0.65, 0, 0.35, 1) infinite',
        // 层进式：整层升起（透明度 + 位移 + 轻微虚化一起收）
        'layer-rise': 'layer-rise 0.62s cubic-bezier(0.22, 1, 0.36, 1) both',
        // 层进式：子项依次侧向滑入（用于模块内部的小块，靠 --d / --i 排延迟）
        'layer-slide': 'layer-slide 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        // 呼吸环：给两大核心模块的图标用，暗示"这里是入口"
        'ring-pulse': 'ring-pulse 2.8s ease-out infinite',
        // 高光扫过：卡片 hover 时光带扫一遍（不是循环，避免整页一直在动）
        'sheen': 'sheen 0.9s ease-out both',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(0, 212, 255, 0.3), 0 0 20px rgba(0, 212, 255, 0.1)' },
          '50%': { boxShadow: '0 0 15px rgba(0, 212, 255, 0.5), 0 0 40px rgba(0, 212, 255, 0.2)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        'gradient-x': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-left': {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        // ------------------------------------------------------------------
        // UI 重设计一轮新增的四组关键帧。
        // 约定：位移一律不超过 56px，时长不超过 0.8s —— 动画是为了"把注意力
        // 引到该看的地方"，不是让页面一直在动（演示时看久了会晕）。
        // ------------------------------------------------------------------
        'chain-pull-left': {
          '0%': { opacity: '0', transform: 'translateX(-56px) scale(0.97)' },
          '60%': { opacity: '1', transform: 'translateX(6px) scale(1.005)' },
          '100%': { opacity: '1', transform: 'translateX(0) scale(1)' },
        },
        'chain-pull-right': {
          '0%': { opacity: '0', transform: 'translateX(56px) scale(0.97)' },
          '60%': { opacity: '1', transform: 'translateX(-6px) scale(1.005)' },
          '100%': { opacity: '1', transform: 'translateX(0) scale(1)' },
        },
        'chain-travel': {
          '0%': { left: '0%', opacity: '0' },
          '12%': { opacity: '1' },
          '88%': { opacity: '1' },
          '100%': { left: '100%', opacity: '0' },
        },
        'layer-rise': {
          '0%': { opacity: '0', transform: 'translateY(22px)', filter: 'blur(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)', filter: 'blur(0)' },
        },
        'layer-slide': {
          '0%': { opacity: '0', transform: 'translateX(-18px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'ring-pulse': {
          '0%': { transform: 'scale(0.85)', opacity: '0.55' },
          '70%': { transform: 'scale(1.6)', opacity: '0' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
        'sheen': {
          '0%': { transform: 'translateX(-120%)', opacity: '0' },
          '35%': { opacity: '0.55' },
          '100%': { transform: 'translateX(120%)', opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
