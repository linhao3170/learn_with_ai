<template>
  <div>
    <h2 class="text-xl font-bold mb-6 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-blue to-neon-purple rounded-full"></span>
      知识点提取
      <span class="text-sm font-normal text-gray-500 ml-2">
        共 {{ totalCount }} 个知识点，{{ categoryCount }} 个分类
      </span>
    </h2>

    <div v-for="(kps, cat) in knowledgeByCategory" :key="cat" class="mb-8">
      <h3 class="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full" :style="{ background: getColor(cat) }"></span>
        {{ cat }}
        <span class="text-xs text-gray-500 font-normal">({{ kps.length }} 个)</span>
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="kp in kps" :key="kp.id" class="knowledge-card group">
          <div class="flex items-start justify-between mb-2">
            <span class="text-sm font-medium text-white">{{ kp.name }}</span>
            <div class="flex items-center gap-0.5 flex-shrink-0 ml-2">
              <span
                v-for="s in 5"
                :key="s"
                class="w-1 h-3 rounded-sm"
                :style="{ background: s <= kp.difficulty ? getColor(cat) : '#1f1f2e' }"
              ></span>
            </div>
          </div>
          <p class="text-[12px] text-gray-500 mb-3 line-clamp-2 leading-relaxed">
            {{ kp.description }}
          </p>
          <div v-if="kp.related_functions?.length > 0" class="flex flex-wrap gap-1">
            <span
              v-for="fn in kp.related_functions.slice(0, 4)"
              :key="fn"
              class="px-1.5 py-0.5 text-[10px] rounded bg-deep-card text-gray-400 font-mono border border-deep-border
                     group-hover:border-neon-purple/30 transition-colors"
            >
              {{ fn }}
            </span>
            <span v-if="kp.related_functions.length > 4" class="text-[10px] text-gray-600 pt-0.5">
              +{{ kp.related_functions.length - 4 }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAnalysisStore, categoryColors } from '../stores/analysis'

const analysis = useAnalysisStore()

const knowledgeByCategory = computed(() => analysis.knowledgeByCategory)
const totalCount = computed(() => analysis.data?.knowledge_points?.length || 0)
const categoryCount = computed(() => Object.keys(knowledgeByCategory.value).length)

function getColor(cat) {
  return categoryColors[cat] || '#00d4ff'
}
</script>
