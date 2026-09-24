<template>
  <div class="flex items-center gap-2 mb-1.5">
    <span class="w-0.5 h-3 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
    <span class="text-xs font-semibold text-gray-300">{{ text }}</span>
    <span v-if="count !== null && count !== undefined" class="text-[10px] text-gray-600 font-mono">{{ count }}</span>
    <span v-if="hint" class="text-[10px] text-gray-600">{{ hint }}</span>
  </div>
</template>

<script setup>
/** 卡片内的小节标题（纯展示）。 */
defineProps({
  text: { type: String, default: '' },
  count: { type: [Number, String], default: null },
  hint: { type: String, default: '' },
})
</script>
