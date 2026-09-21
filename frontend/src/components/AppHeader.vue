<template>
  <header class="fixed top-0 left-0 right-0 z-50 border-b border-deep-border/50 bg-deep-surface/70 backdrop-blur-xl">
    <div class="max-w-[1920px] mx-auto px-6 h-14 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue via-neon-purple to-neon-pink flex items-center justify-center animate-glow-pulse">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 18 22 12 16 6"></polyline>
            <polyline points="8 6 2 12 8 18"></polyline>
          </svg>
        </div>
        <div>
          <div class="text-sm font-bold tracking-wide gradient-text">LearnWithAI</div>
          <div class="text-[10px] text-gray-500 font-mono tracking-wider">BUSINESS LOGIC ANALYZER v0.1</div>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          v-if="hasData"
          @click="$emit('reset')"
          class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-white border border-deep-border rounded-lg transition-all hover:border-neon-blue/30 hover:bg-neon-blue/5"
        >
          重新选择
        </button>
        <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-deep-card border border-deep-border">
          <div class="w-2 h-2 rounded-full bg-neon-green animate-pulse"></div>
          <span class="text-[11px] text-gray-400 font-mono">ENGINE ONLINE</span>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
defineProps({
  hasData: Boolean,
})

defineEmits(['reset'])
</script>
