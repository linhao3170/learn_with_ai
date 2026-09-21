<template>
  <div class="deep-analysis-view">
    <h2 class="text-xl font-bold mb-4 flex items-center gap-2">
      <span class="w-1 h-5 bg-gradient-to-b from-neon-purple to-neon-blue rounded-full"></span>
      深度业务分析
    </h2>

    <!-- Tab Navigation -->
    <div class="flex gap-2 mb-5 flex-wrap">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Architecture View -->
    <div v-show="activeTab === 'architecture'">
      <div class="glass-card p-6 relative overflow-hidden">
        <div class="scan-line"></div>
        <div v-if="!architecture" class="text-gray-500 text-sm py-12 text-center">
          暂无架构分析数据
        </div>
        <svg v-else :viewBox="archViewBox" class="w-full" :style="{ minHeight: archHeight + 'px' }">
          <!-- Definitions -->
          <defs>
            <linearGradient id="arch-card-orchestration" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#8b5cf6;stop-opacity:0.3" />
              <stop offset="100%" style="stop-color:#6366f1;stop-opacity:0.1" />
            </linearGradient>
            <linearGradient id="arch-card-business" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#06b6d4;stop-opacity:0.3" />
              <stop offset="100%" style="stop-color:#0ea5e9;stop-opacity:0.1" />
            </linearGradient>
            <linearGradient id="arch-card-support" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#10b981;stop-opacity:0.3" />
              <stop offset="100%" style="stop-color:#22c55e;stop-opacity:0.1" />
            </linearGradient>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
            </marker>
          </defs>

          <!-- Edges -->
          <g class="edges">
            <path
              v-for="(edge, idx) in archEdges"
              :key="'edge-'+idx"
              :d="edge.path"
              fill="none"
              :stroke="edge.color"
              :stroke-width="edge.width"
              stroke-opacity="0.6"
              marker-end="url(#arrowhead)"
              class="transition-all duration-300"
              :class="{ 'hover:stroke-opacity-100': true }"
            />
          </g>

          <!-- Module Nodes -->
          <g
            v-for="node in archNodes"
            :key="node.module_id"
            class="cursor-pointer transition-all duration-300 hover:opacity-90"
            :transform="'translate(' + node.x + ',' + node.y + ')'"
            @click="selectNode(node)"
          >
            <rect
              :width="node.width"
              :height="node.height"
              rx="8"
              :fill="'url(#arch-card-' + node.layer + ')'"
              :stroke="nodeColor(node.layer)"
              stroke-width="1.5"
              :class="{ 'stroke-neon-purple': selectedNode?.module_id === node.module_id }"
            />
            <text
              :x="node.width / 2"
              :y="node.height / 2 - 6"
              text-anchor="middle"
              fill="white"
              font-size="13"
              font-weight="600"
            >{{ node.display_name }}</text>
            <text
              :x="node.width / 2"
              :y="node.height / 2 + 12"
              text-anchor="middle"
              fill="#94a3b8"
              font-size="10"
            >{{ node.method_count }} methods | {{ node.role }}</text>
          </g>
        </svg>

        <!-- Legend -->
        <div class="flex gap-4 mt-4 text-xs text-gray-400 justify-center flex-wrap">
          <div class="flex items-center gap-1.5">
            <span class="w-3 h-3 rounded bg-neon-purple/50 border border-neon-purple"></span>
            编排层
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-3 h-3 rounded bg-neon-blue/50 border border-neon-blue"></span>
            业务层
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-3 h-3 rounded bg-green-500/50 border border-green-500"></span>
            支撑层
          </div>
        </div>
      </div>

      <!-- Selected module details -->
      <div v-if="selectedNode" class="glass-card p-5 mt-4">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold text-white">{{ selectedNode.display_name }}</h3>
          <span class="text-xs px-2 py-0.5 rounded-full" :class="roleBadgeClass(selectedNode.role)">
            {{ roleLabel(selectedNode.role) }}
          </span>
        </div>
        <div class="grid grid-cols-3 gap-4 text-sm mb-3">
          <div>
            <div class="text-gray-500 text-xs">方法数</div>
            <div class="text-white font-mono font-bold">{{ selectedNode.method_count }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">依赖</div>
            <div class="text-white font-mono font-bold">{{ moduleDeps(selectedNode.module_id)?.out || 0 }}</div>
          </div>
          <div>
            <div class="text-gray-500 text-xs">被依赖</div>
            <div class="text-white font-mono font-bold">{{ moduleDeps(selectedNode.module_id)?.in || 0 }}</div>
          </div>
        </div>
        <div v-if="selectedNode.responsibilities?.length" class="flex flex-wrap gap-1.5">
          <span
            v-for="(r, i) in selectedNode.responsibilities"
            :key="i"
            class="text-xs px-2 py-0.5 rounded bg-deep-card text-gray-300 border border-deep-border"
          >{{ r }}</span>
        </div>
      </div>
    </div>

    <!-- Business Flows -->
    <div v-show="activeTab === 'flows'">
      <div v-if="!flows || !flows.length" class="text-gray-500 text-sm py-12 text-center glass-card">
        暂无业务流程数据
      </div>
      <div v-else class="space-y-4">
        <!-- Flow selector -->
        <div class="flex gap-2 flex-wrap">
          <button
            v-for="(flow, idx) in flows"
            :key="flow.flow_id"
            @click="selectedFlowIdx = idx"
            class="px-4 py-2 rounded-lg text-sm transition-all border"
            :class="selectedFlowIdx === idx
              ? 'border-neon-blue bg-neon-blue/10 text-neon-blue'
              : 'border-deep-border text-gray-400 hover:border-neon-blue/40 hover:text-white'"
          >
            {{ flow.name }}
          </button>
        </div>

        <!-- Flow detail -->
        <div v-if="selectedFlow" class="glass-card p-6">
          <div class="flex items-start justify-between mb-4">
            <div>
              <h3 class="font-bold text-white text-lg">{{ selectedFlow.name }}</h3>
              <p class="text-gray-400 text-sm mt-1">{{ selectedFlow.description }}</p>
            </div>
            <div class="flex gap-2 flex-wrap">
              <span class="text-xs px-2 py-1 rounded bg-neon-blue/10 text-neon-blue border border-neon-blue/20">
                {{ selectedFlow.modules_involved?.length || 0 }} 个模块
              </span>
              <span class="text-xs px-2 py-1 rounded bg-neon-purple/10 text-neon-purple border border-neon-purple/20">
                {{ selectedFlow.steps?.length || 0 }} 个步骤
              </span>
              <span v-if="selectedFlow.has_state_change" class="text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                状态变更
              </span>
              <span v-if="selectedFlow.has_validation" class="text-xs px-2 py-1 rounded bg-green-500/10 text-green-400 border border-green-500/20">
                校验
              </span>
            </div>
          </div>

          <!-- Flow steps timeline -->
          <div class="flow-steps relative pl-4">
            <div class="absolute left-1.5 top-2 bottom-2 w-px bg-deep-border"></div>
            <div
              v-for="(step, idx) in selectedFlow.steps"
              :key="step.step_id"
              class="relative pb-4 last:pb-0"
            >
              <div
                class="absolute -left-4 top-1.5 w-3 h-3 rounded-full border-2"
                :class="stepDotClass(step)"
              ></div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs text-gray-500 font-mono w-6">{{ step.order }}.</span>
                <span class="font-mono text-sm text-white">{{ step.method }}</span>
                <span class="text-xs px-1.5 py-0.5 rounded bg-deep-card text-gray-400">
                  {{ step.module }}
                </span>
                <span v-if="step.is_module_boundary" class="text-xs px-1.5 py-0.5 rounded bg-neon-purple/20 text-neon-purple">
                  跨模块
                </span>
                <span v-if="step.is_state_change" class="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                  状态变更
                </span>
                <span v-if="step.is_validation" class="text-xs px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
                  校验
                <span v-if="step.line" 
                      class="text-[10px] text-gray-600 font-mono cursor-pointer hover:text-neon-blue transition-colors inline-flex items-center gap-1 ml-1"
                      @click.stop="openStepSource(step)">
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                  L{{ step.line }}
                </span>
                </span>
              </div>
              <div v-if="step.description" class="text-xs text-gray-500 mt-1 ml-6">
                {{ step.description }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Evidence-aware business priority -->
    <div v-show="activeTab === 'priority'">
      <div v-if="!businessPriority?.summary" class="text-gray-500 text-sm py-12 text-center glass-card">
        暂无业务优先级数据
      </div>
      <div v-else class="space-y-4">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="glass-card p-4">
            <div class="text-xs text-gray-500">核心节点</div>
            <div class="text-2xl font-bold text-neon-blue mt-1">{{ businessPriority.summary.total_nodes }}</div>
            <div class="text-xs text-gray-500 mt-1">按结构信号排序</div>
          </div>
          <div class="glass-card p-4">
            <div class="text-xs text-gray-500">业务流程</div>
            <div class="text-2xl font-bold text-neon-purple mt-1">{{ businessPriority.summary.total_flows }}</div>
            <div class="text-xs text-gray-500 mt-1">已提取并评分</div>
          </div>
          <div class="glass-card p-4">
            <div class="text-xs text-gray-500">证据完整度</div>
            <div class="text-2xl font-bold text-emerald-400 mt-1">
              {{ Math_round((businessPriority.summary.evidence_completeness || 0) * 100) }}%
            </div>
            <div class="text-xs text-gray-500 mt-1">行号/位置证据</div>
          </div>
          <div class="glass-card p-4">
            <div class="text-xs text-gray-500">待审核提示</div>
            <div class="text-2xl font-bold text-amber-400 mt-1">{{ businessPriority.summary.review_gap_count || 0 }}</div>
            <div class="text-xs text-gray-500 mt-1">不自动判定为错误</div>
          </div>
        </div>

        <div class="glass-card p-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-bold text-white">核心业务节点</h3>
              <p class="text-xs text-gray-500 mt-1">用于确定讲解和教师审核顺序，结论仍需回到代码证据。</p>
            </div>
            <span class="text-xs px-2 py-1 rounded bg-neon-blue/10 text-neon-blue border border-neon-blue/20">
              {{ businessPriority.algorithm?.version || 'BLPS' }}
            </span>
          </div>
          <div class="space-y-2">
            <div v-for="(node, idx) in priorityNodes.slice(0, 8)" :key="node.node_id"
                 class="flex items-center gap-3 p-3 rounded-lg bg-deep-card border border-deep-border">
              <span class="text-xs font-mono text-gray-500 w-5">#{{ idx + 1 }}</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-mono text-sm text-white">{{ node.method }}</span>
                  <span class="text-xs px-1.5 py-0.5 rounded bg-neon-purple/10 text-neon-purple">{{ node.module }}</span>
                </div>
                <div class="flex flex-wrap gap-1 mt-1">
                  <span v-for="reason in node.reasons" :key="reason" class="text-[10px] text-gray-400">{{ reason }}</span>
                </div>
                <div class="text-[10px] text-gray-500 font-mono mt-1 cursor-pointer hover:text-neon-blue transition-colors inline-flex items-center gap-1"
                     @click.stop="openSourceFromLocation(node.location, node.method + ' - 核心业务节点')">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                  {{ node.location }}
                </div>
              </div>
                <!-- Five-dimension metric breakdown -->
                <div class="mt-2 grid grid-cols-5 gap-1.5">
                  <div class="text-center">
                    <div class="h-1 bg-deep-border rounded-full overflow-hidden">
                      <div class="h-full bg-sky-400" :style="{ width: Math.round(node.metrics.centrality * 100) + '%' }"></div>
                    </div>
                    <div class="text-[9px] text-gray-500 mt-0.5">中心性</div>
                  </div>
                  <div class="text-center">
                    <div class="h-1 bg-deep-border rounded-full overflow-hidden">
                      <div class="h-full bg-violet-400" :style="{ width: Math.round(node.metrics.flow_reachability * 100) + '%' }"></div>
                    </div>
                    <div class="text-[9px] text-gray-500 mt-0.5">流程参与</div>
                  </div>
                  <div class="text-center">
                    <div class="h-1 bg-deep-border rounded-full overflow-hidden">
                      <div class="h-full bg-amber-400" :style="{ width: Math.round(node.metrics.state_mutation * 100) + '%' }"></div>
                    </div>
                    <div class="text-[9px] text-gray-500 mt-0.5">状态变更</div>
                  </div>
                  <div class="text-center">
                    <div class="h-1 bg-deep-border rounded-full overflow-hidden">
                      <div class="h-full bg-pink-400" :style="{ width: Math.round(node.metrics.boundary_role * 100) + '%' }"></div>
                    </div>
                    <div class="text-[9px] text-gray-500 mt-0.5">跨模块</div>
                  </div>
                  <div class="text-center">
                    <div class="h-1 bg-deep-border rounded-full overflow-hidden">
                      <div class="h-full bg-emerald-400" :style="{ width: Math.round(node.metrics.evidence_completeness * 100) + '%' }"></div>
                    </div>
                    <div class="text-[9px] text-gray-500 mt-0.5">证据完整</div>
                  </div>
                </div>
              <div class="w-24 flex-shrink-0">
                <div class="text-right text-sm font-bold text-neon-blue">{{ node.score.toFixed(1) }}</div>
                <div class="h-1.5 bg-deep-border rounded-full overflow-hidden mt-1">
                  <div class="h-full rounded-full bg-gradient-to-r from-neon-blue to-neon-purple" :style="{ width: Math.min(100, node.score) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="glass-card p-5">
          <h3 class="font-bold text-white mb-3">业务流程优先级</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div v-for="flow in priorityFlows" :key="flow.flow_id" class="p-3 rounded-lg bg-deep-card border border-deep-border">
              <div class="flex items-start justify-between gap-3">
                <div class="text-sm font-semibold text-white">{{ flow.name }}</div>
                <span class="text-sm font-bold text-neon-blue">{{ flow.priority_score.toFixed(1) }}</span>
              </div>
              <div class="flex flex-wrap gap-1.5 mt-2">
                <span v-for="reason in flow.reasons" :key="reason" class="text-[10px] px-1.5 py-0.5 rounded bg-deep-surface text-gray-400">{{ reason }}</span>
              </div>
              <div v-if="flow.review_risk > 0" class="text-xs text-amber-400 mt-2">
                审核提示：{{ flow.review_risk.toFixed(1) }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="priorityGaps.length" class="glass-card p-5 border-amber-500/20">
          <h3 class="font-bold text-amber-300 mb-3">建议先审核的证据缺口</h3>
          <div class="space-y-2">
            <div v-for="gap in priorityGaps" :key="gap.type + gap.flow_id" class="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
              <div class="text-sm text-amber-200">{{ gap.title }}</div>
              <div class="text-xs text-gray-400 mt-1">{{ gap.description }}</div>
              <div class="text-[10px] text-gray-500 font-mono mt-1 cursor-pointer hover:text-amber-300 transition-colors inline-flex items-center gap-1"
                   @click.stop="openSourceFromLocation(gap.location, gap.title)">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                {{ gap.location }}
              </div>
            </div>
          </div>
        </div>

        <details class="glass-card p-5">
          <summary class="cursor-pointer text-sm font-semibold text-gray-300">查看算法口径（可复现）</summary>
          <div class="mt-3 text-xs text-gray-400 space-y-2">
            <div>节点评分：{{ businessPriority.algorithm?.formula }}</div>
            <div>PageRank：{{ businessPriority.algorithm?.pagerank }}</div>
            <div>{{ businessPriority.algorithm?.caveat }}</div>
          </div>
        </details>
      </div>
    </div>

    <!-- Design Patterns -->
    <div v-show="activeTab === 'patterns'">
      <div v-if="!designPatterns.length" class="text-gray-500 text-sm py-12 text-center glass-card">
        No design patterns detected
      </div>
      <div v-else class="space-y-4">
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          <button
            v-for="(pattern, idx) in designPatterns"
            :key="pattern.pattern_id + '_' + pattern.target_name"
            @click="selectedPatternIdx = idx"
            class="p-3 rounded-lg text-left transition-all border"
            :class="selectedPatternIdx === idx
              ? 'border-neon-purple bg-neon-purple/10'
              : 'border-deep-border hover:border-neon-purple/40'"
          >
            <div class="text-sm font-semibold text-white">{{ pattern.pattern_name }}</div>
            <div class="text-xs text-gray-400 mt-1">{{ pattern.target_name }}</div>
            <div class="flex items-center gap-2 mt-2">
              <div class="flex-1 h-1.5 bg-deep-border rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-neon-purple to-neon-blue rounded-full"
                     :style="{ width: (pattern.score * 100) + '%' }"></div>
              </div>
              <span class="text-xs text-gray-500 font-mono">{{ Math_round(pattern.score * 100) }}%</span>
            </div>
          </button>
        </div>
        <div v-if="selectedPattern" class="glass-card p-5">
          <div class="flex items-start justify-between mb-3">
            <div>
              <h3 class="font-bold text-white text-lg">{{ selectedPattern.pattern_name }}</h3>
              <p class="text-gray-400 text-sm mt-1">{{ selectedPattern.description }}</p>
            </div>
            <div class="flex gap-2 flex-wrap">
              <span class="text-xs px-2 py-0.5 rounded bg-neon-purple/10 text-neon-purple border border-neon-purple/20">
                {{ selectedPattern.category }}
              </span>
              <span class="text-xs px-2 py-0.5 rounded bg-neon-blue/10 text-neon-blue border border-neon-blue/20">
                {{ selectedPattern.confidence }}
              </span>
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Evidence</div>
              <div class="space-y-2">
                <div v-for="(ev, i) in selectedPattern.evidence" :key="i"
                     class="flex items-start gap-2 text-sm">
                  <span class="text-neon-green mt-0.5">&#9679;</span>
                  <div>
                    <span class="text-gray-300">{{ ev.description }}</span>
                    <span v-if="ev.line_start" class="text-gray-600 text-xs ml-2 font-mono">
                      L{{ ev.line_start }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div>
              <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Target</div>
              <div class="text-sm text-gray-300 space-y-1">
                <div><span class="text-gray-500">Type:</span> {{ selectedPattern.target_type }}</div>
                <div><span class="text-gray-500">Name:</span> <code class="text-neon-blue">{{ selectedPattern.target_name }}</code></div>
                <div v-if="selectedPattern.related_classes?.length">
                  <span class="text-gray-500">Related:</span>
                  <span v-for="(c, i) in selectedPattern.related_classes" :key="c"
                        class="text-xs px-1.5 py-0.5 bg-deep-card rounded text-gray-300 ml-1">{{ c }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Key Implementations -->
    <div v-show="activeTab === 'key_impls'">
      <!-- 教师审核模式开关 -->
      <div class="mb-4 flex items-center justify-between glass-card p-4">
        <div class="flex items-center gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              v-model="reviewMode"
              class="w-4 h-4 rounded border-gray-600 bg-deep-card text-neon-blue focus:ring-neon-blue focus:ring-offset-0"
            />
            <span class="text-sm font-medium text-gray-300">教师审核模式</span>
          </label>
          <span class="text-xs text-gray-500">
            (审核 inferred 级别的推断结论)
          </span>
        </div>
        <div v-if="reviewMode" class="flex items-center gap-4 text-xs">
          <div class="flex items-center gap-1">
            <span class="w-3 h-3 rounded-full bg-emerald-500"></span>
            <span class="text-gray-400">已确认: {{ Object.values(reviewStatus).filter(s => s === 'confirmed').length }}</span>
          </div>
          <div class="flex items-center gap-1">
            <span class="w-3 h-3 rounded-full bg-red-500"></span>
            <span class="text-gray-400">已拒绝: {{ Object.values(reviewStatus).filter(s => s === 'rejected').length }}</span>
          </div>
        </div>
      </div>

      <div v-if="!keyImplementations.length" class="text-gray-500 text-sm py-12 text-center glass-card">
        No key implementations identified
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="(impl, idx) in keyImplementations"
          :key="impl.node_id"
          @click="selectedKeyImplIdx = idx"
          class="p-4 rounded-lg cursor-pointer transition-all border"
          :class="selectedKeyImplIdx === idx
            ? 'border-neon-blue bg-neon-blue/5'
            : 'border-deep-border hover:border-neon-blue/40'"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-mono text-gray-500 w-6">#{{ idx + 1 }}</span>
                <span class="font-mono text-white font-semibold">{{ impl.method }}</span>
                <span v-if="impl.class" class="text-gray-400 text-sm">in {{ impl.class }}</span>
              </div>
              <div class="text-xs text-gray-500 mt-1 font-mono cursor-pointer hover:text-neon-blue transition-colors inline-flex items-center gap-1"
                   @click.stop="openSource(impl.filepath, impl.start_line, impl.end_line, impl.method + ' - 关键实现')">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                {{ impl.module }} &middot; L{{ impl.start_line }}-{{ impl.end_line }}
              </div>
              <div class="mt-2 flex flex-wrap gap-1.5">
                <span v-for="(char, cIdx) in (impl.design_characteristics || []).slice(0, 3)" :key="cIdx"
                      :class="[
                        'text-xs px-2 py-0.5 rounded',
                        char.confidence === 'verified' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-amber-900/30 text-amber-400'
                      ]">
                  {{ char.label }}
                </span>
              </div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-2xl font-bold text-neon-blue">{{ impl.importance_score }}</div>
              <div class="text-xs text-gray-500">score</div>
            </div>
          </div>
          <div v-if="selectedKeyImplIdx === idx" class="mt-4 pt-4 border-t border-deep-border">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div class="bg-deep-card rounded p-3">
                <div class="text-xs text-gray-500">Complexity</div>
                <div class="text-lg font-bold text-white font-mono">{{ impl.complexity }}</div>
              </div>
              <div class="bg-deep-card rounded p-3">
                <div class="text-xs text-gray-500">Algorithm</div>
                <div class="text-sm font-semibold" :class="impl.algorithm_hints?.confidence === 'verified' ? 'text-emerald-400' : 'text-amber-400'">
                  {{ impl.algorithm_hints?.detected || impl.algorithm_type || 'N/A' }}
                </div>
                <div v-if="impl.algorithm_hints?.confidence === 'inferred'" class="text-xs text-gray-500 mt-0.5">
                  (待确认)
                </div>
              </div>
              <div class="bg-deep-card rounded p-3">
                <div class="text-xs text-gray-500">Guards</div>
                <div class="text-lg font-bold text-white font-mono">{{ (impl.guard_clauses || []).length }}</div>
              </div>
              <div class="bg-deep-card rounded p-3">
                <div class="text-xs text-gray-500">Edges</div>
                <div class="text-lg font-bold text-white font-mono">{{ (impl.edge_cases || []).length }}</div>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-if="impl.design_characteristics?.length" class="md:col-span-2">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Design Characteristics</div>
                <div class="space-y-2">
                  <div v-for="(char, cIdx) in impl.design_characteristics" :key="cIdx"
                       class="bg-deep-card rounded p-3 border-l-2"
                       :class="char.confidence === 'verified' ? 'border-emerald-500' : 'border-amber-500'">
                    <div class="flex items-start justify-between gap-2">
                      <div class="flex-1">
                        <div class="text-sm font-semibold"
                             :class="char.confidence === 'verified' ? 'text-emerald-400' : 'text-amber-400'">
                          {{ char.label }}
                        </div>
                        <div class="text-xs text-gray-500 mt-1">
                          <span class="text-gray-600">证据:</span> {{ char.evidence }}
                        </div>
                      </div>
                      <span class="text-xs px-2 py-0.5 rounded flex-shrink-0"
                            :class="char.confidence === 'verified' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-amber-900/30 text-amber-400'">
                        {{ char.confidence === 'verified' ? '已验证' : '待确认' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="impl.algorithm_hints?.reason">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Algorithm Analysis</div>
                <div class="bg-deep-card rounded p-3">
                  <div class="text-sm font-semibold mb-1"
                       :class="impl.algorithm_hints.confidence === 'verified' ? 'text-emerald-400' : 'text-amber-400'">
                    {{ impl.algorithm_hints.detected }}
                  </div>
                  <div class="text-xs text-gray-500">
                    <span class="text-gray-600">推断依据:</span> {{ impl.algorithm_hints.reason }}
                  </div>
                  <div class="text-xs mt-2 px-2 py-0.5 rounded inline-block"
                       :class="impl.algorithm_hints.confidence === 'verified' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-amber-900/30 text-amber-400'">
                    {{ impl.algorithm_hints.confidence === 'verified' ? '结构验证' : '需教师确认' }}
                  </div>
                </div>
              </div>
              <div v-if="impl.importance_reasons?.length">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Why Key</div>
                <div class="space-y-1">
                  <div v-for="(reason, i) in impl.importance_reasons" :key="i"
                       class="text-sm text-gray-300 flex items-start gap-2">
                    <span class="text-amber-400 mt-0.5">&#9733;</span>
                    <span>{{ reason }}</span>
                  </div>
                </div>
              </div>
              <div v-if="impl.design_pattern">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Design Pattern</div>
                <div class="text-sm text-neon-purple font-semibold">{{ impl.design_pattern }}</div>
              </div>
              <div v-if="impl.edge_cases?.length">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Edge Cases</div>
                <div class="space-y-1">
                  <div v-for="(ec, i) in impl.edge_cases.slice(0, 6)" :key="i"
                       class="text-sm text-gray-300 font-mono bg-deep-card px-2 py-1 rounded">
                    {{ ec }}
                  </div>
                </div>
              </div>
              <div v-if="impl.state_writes?.length">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">State Mutations</div>
                <div class="flex flex-wrap gap-1">
                  <span v-for="s in impl.state_writes" :key="s"
                        class="text-xs px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded font-mono">
                    {{ s }}
                  </span>
                </div>
              </div>
              <div v-if="impl.loop_patterns?.length">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Loop Patterns</div>
                <div class="flex flex-wrap gap-1">
                  <span v-for="lp in impl.loop_patterns" :key="lp"
                        class="text-xs px-2 py-0.5 bg-neon-green/10 text-neon-green border border-neon-green/20 rounded">
                    {{ lp }}
                  </span>
                </div>
              </div>
              <div v-if="impl.categories?.length">
                <div class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Categories</div>
                <div class="flex flex-wrap gap-1">
                  <span v-for="cat in impl.categories" :key="cat"
                        class="text-xs px-2 py-0.5 bg-deep-card text-gray-300 rounded">
                    {{ cat }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 教师审核区域 -->
            <div v-if="reviewMode" class="mt-4 pt-4 border-t border-deep-border">
              <div class="text-xs text-gray-500 mb-3 uppercase tracking-wider">教师审核</div>

              <!-- 如果已审核，显示状态 -->
              <div v-if="getReviewStatus(impl.node_id)" class="space-y-2">
                <div v-if="getReviewStatus(impl.node_id) === 'confirmed'"
                     class="flex items-center justify-between p-3 rounded bg-emerald-900/20 border border-emerald-500/30">
                  <div class="flex items-center gap-2">
                    <span class="text-emerald-400 text-lg">✓</span>
                    <span class="text-sm text-emerald-300">已确认：所有推断结论经教师验证为准确</span>
                  </div>
                  <button @click="clearReview(impl.node_id)"
                          class="text-xs px-2 py-1 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors">
                    撤销
                  </button>
                </div>

                <div v-else-if="getReviewStatus(impl.node_id) === 'rejected'"
                     class="flex items-center justify-between p-3 rounded bg-red-900/20 border border-red-500/30">
                  <div class="flex items-center gap-2">
                    <span class="text-red-400 text-lg">✗</span>
                    <span class="text-sm text-red-300">已拒绝：教师标记此实现分析不准确</span>
                  </div>
                  <button @click="clearReview(impl.node_id)"
                          class="text-xs px-2 py-1 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">
                    撤销
                  </button>
                </div>
              </div>

              <!-- 如果未审核，显示审核按钮 -->
              <div v-else class="flex items-center gap-3">
                <button @click="confirmImplementation(impl.node_id)"
                        class="flex-1 px-4 py-2 rounded bg-emerald-900/20 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-900/30 transition-colors flex items-center justify-center gap-2">
                  <span class="text-lg">✓</span>
                  <span class="text-sm font-medium">确认准确</span>
                </button>
                <button @click="rejectImplementation(impl.node_id)"
                        class="flex-1 px-4 py-2 rounded bg-red-900/20 border border-red-500/30 text-red-400 hover:bg-red-900/30 transition-colors flex items-center justify-center gap-2">
                  <span class="text-lg">✗</span>
                  <span class="text-sm font-medium">标记错误</span>
                </button>
              </div>

              <div class="mt-2 text-xs text-gray-500">
                提示：仅对 <span class="text-amber-400">待确认</span> 级别的推断结论进行审核，<span class="text-emerald-400">已验证</span> 的结构性事实无需审核。
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

       <!-- Call Graph -->
   <div v-show="activeTab === 'callgraph'">
     <div class="glass-card p-6">
       <div v-if="!callGraph" class="text-gray-500 text-sm py-12 text-center">
         暂无调用图数据
       </div>
        <template v-else>
          <!-- Stats bar -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <div class="text-center">
              <div class="text-2xl font-bold text-neon-blue font-mono">{{ callGraph.total_nodes }}</div>
              <div class="text-xs text-gray-500 mt-1">节点（方法/函数）</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-neon-purple font-mono">{{ callGraph.total_edges }}</div>
              <div class="text-xs text-gray-500 mt-1">调用边</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-green-400 font-mono">{{ callGraph.entry_points?.length || 0 }}</div>
              <div class="text-xs text-gray-500 mt-1">入口点</div>
            </div>
            <div class="text-center">
              <div class="text-2xl font-bold text-amber-400 font-mono">{{ callGraph.leaves?.length || 0 }}</div>
              <div class="text-xs text-gray-500 mt-1">叶子节点</div>
            </div>
          </div>

          <!-- Controls -->
          <div class="flex gap-3 mb-4 flex-wrap items-center">
            <div class="relative flex-1 min-w-[200px]">
              <input
                v-model="cgSearch"
                type="text"
                placeholder="搜索方法名..."
                class="w-full px-4 py-2 pl-9 text-sm bg-deep-card border border-deep-border rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-neon-blue/50"
              />
              <svg class="absolute left-3 top-2.5 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="8" stroke-width="2"/>
                <path d="m21 21-4.3-4.3" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <div class="flex gap-1 flex-wrap">
              <button
                v-for="mod in cgModuleList"
                :key="mod.id"
                @click="toggleModuleFilter(mod.id)"
                class="px-3 py-1.5 text-xs rounded-lg border transition-all"
                :class="cgModuleFilter.has(mod.id)
                  ? 'border-transparent text-white'
                  : 'border-deep-border text-gray-500 hover:border-gray-500'"
                :style="cgModuleFilter.has(mod.id) ? { background: mod.color + '25', borderColor: mod.color + '50' } : {}"
              >
                {{ mod.shortName }}
              </button>
            </div>
          </div>

          <!-- Call graph SVG -->
          <div class="relative overflow-auto border border-deep-border rounded-xl bg-deep-card/30" :style="{ maxHeight: '500px' }">
            <svg
              :viewBox="cgViewBox"
              class="w-full"
              :style="{ minWidth: cgMinWidth + 'px', minHeight: cgTotalHeight + 'px' }"
            >
              <defs>
                <marker
                  id="cg-arrowhead"
                  markerWidth="8"
                  markerHeight="6"
                  refX="7"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 8 3, 0 6" fill="#64748b" />
                </marker>
                <marker
                  id="cg-arrowhead-highlight"
                  markerWidth="8"
                  markerHeight="6"
                  refX="7"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 8 3, 0 6" fill="#a855f7" />
                </marker>
                <linearGradient id="cg-glow-entry" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" style="stop-color:#10b981;stop-opacity:0.3" />
                  <stop offset="100%" style="stop-color:#06b6d4;stop-opacity:0.1" />
                </linearGradient>
              </defs>

              <!-- Layer backgrounds -->
              <g class="cg-layers">
                <rect
                  v-for="(layer, idx) in cgLayers"
                  :key="'layer-bg-'+idx"
                  :x="layer.x"
                  :y="0"
                  :width="layer.width"
                  :height="cgTotalHeight"
                  :fill="idx % 2 === 0 ? 'rgba(15,23,42,0.3)' : 'rgba(30,41,59,0.2)'"
                />
              </g>

              <!-- Layer labels -->
              <g class="cg-layer-labels">
                <text
                  v-for="(layer, idx) in cgLayers"
                  :key="'layer-label-'+idx"
                  :x="layer.x + layer.width / 2"
                  :y="20"
                  text-anchor="middle"
                  fill="#64748b"
                  font-size="11"
                  font-weight="500"
                >{{ layer.label }}</text>
              </g>

              <!-- Edges -->
              <g class="cg-edges">
                <path
                  v-for="(edge, idx) in cgVisibleEdges"
                  :key="'edge-'+idx"
                  :d="edge.path"
                  fill="none"
                  :stroke="edge.highlighted ? '#a855f7' : '#475569'"
                  :stroke-width="edge.highlighted ? 2 : 1.2"
                  :stroke-opacity="edge.highlighted ? 0.9 : 0.5"
                  :marker-end="edge.highlighted ? 'url(#cg-arrowhead-highlight)' : 'url(#cg-arrowhead)'"
                  class="transition-all duration-200"
                />
              </g>

              <!-- Nodes -->
              <g class="cg-nodes">
                <g
                  v-for="node in cgVisibleNodes"
                  :key="node.id"
                  :transform="'translate(' + node.x + ',' + node.y + ')'"
                  class="cursor-pointer transition-all duration-200"
                  @click="selectCgNode(node)"
                >
                  <rect
                    :width="node.width"
                    :height="node.height"
                    rx="6"
                    :fill="node.isEntry ? 'url(#cg-glow-entry)' : (node.color + '15')"
                    :stroke="cgSelectedNode?.id === node.id ? '#fff' : (node.color + '80')"
                    :stroke-width="cgSelectedNode?.id === node.id ? 2 : 1.2"
                    class="transition-all duration-200"
                  />
                  <text
                    :x="node.width / 2"
                    :y="node.height / 2 - 2"
                    text-anchor="middle"
                    fill="#e2e8f0"
                    font-size="11"
                    font-weight="500"
                    font-family="ui-monospace, monospace"
                  >{{ node.shortName }}</text>
                  <text
                    :x="node.width / 2"
                    :y="node.height / 2 + 10"
                    text-anchor="middle"
                    :fill="node.color"
                    font-size="9"
                  >{{ node.moduleShort }}</text>
                  <circle
                    v-if="node.isEntry"
                    :cx="node.width - 6"
                    :cy="6"
                    r="4"
                    fill="#10b981"
                  >
                    <title>入口点</title>
                  </circle>
                </g>
              </g>
            </svg>
          </div>

          <!-- Legend -->
          <div class="flex gap-4 mt-3 text-xs text-gray-400 justify-center flex-wrap">
            <div class="flex items-center gap-1.5">
              <span class="w-3 h-3 rounded-full bg-green-500"></span>
              入口方法
            </div>
            <div class="flex items-center gap-1.5">
              <span class="w-3 h-3 rounded border border-gray-500" style="background: rgba(100,116,139,0.2)"></span>
              内部方法
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-gray-500">→</span>
              调用方向
            </div>
          </div>
        </template>

        <!-- Selected node detail -->
        <transition name="slide-up">
          <div v-if="cgSelectedNode" class="mt-4 glass-card p-5 border border-deep-border">
            <div class="flex items-start justify-between mb-3">
              <div>
                <div class="font-mono font-bold text-white">{{ cgSelectedNode.name }}</div>
                <div class="text-xs text-gray-500 mt-0.5">
                  {{ cgSelectedNode.module }} :: {{ cgSelectedNode.class }}
                  <span v-if="cgSelectedNode.isEntry" class="ml-2 px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">入口点</span>
                </div>
              </div>
              <button @click="cgSelectedNode = null" class="text-gray-500 hover:text-white transition-colors text-lg leading-none">×</button>
            </div>
            <div class="grid grid-cols-3 gap-3 text-sm mb-3">
              <div>
                <div class="text-gray-500 text-xs">调用数</div>
                <div class="text-white font-mono font-bold">{{ cgSelectedNode.outDegree }}</div>
              </div>
              <div>
                <div class="text-gray-500 text-xs">被调用数</div>
                <div class="text-white font-mono font-bold">{{ cgSelectedNode.inDegree }}</div>
              </div>
              <div>
                <div class="text-gray-500 text-xs">代码行</div>
                <div class="text-white font-mono font-bold">{{ cgSelectedNode.lineCount }}</div>
              </div>
            </div>
            <div v-if="cgSelectedNode.tags?.length" class="flex gap-1.5 flex-wrap mb-3">
              <span
                v-for="tag in cgSelectedNode.tags"
                :key="tag"
                class="text-[10px] px-2 py-0.5 rounded-full bg-deep-card text-gray-400 border border-deep-border"
              >{{ tag }}</span>
            </div>
            <div v-if="cgSelectedNode.calls?.length" class="mb-2">
              <div class="text-xs text-gray-500 mb-1">调用了：</div>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="c in cgSelectedNode.calls.slice(0,6)"
                  :key="c.to"
                  class="text-[10px] px-2 py-0.5 rounded bg-neon-purple/10 text-neon-purple border border-neon-purple/20 font-mono"
                >{{ c.to.split(':').pop() }}</span>
                <span v-if="cgSelectedNode.calls.length > 6" class="text-[10px] text-gray-500 px-2 py-0.5">+{{ cgSelectedNode.calls.length - 6 }} 更多</span>
              </div>
            </div>
            <div v-if="cgSelectedNode.calledBy?.length">
              <div class="text-xs text-gray-500 mb-1">被谁调用：</div>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="c in cgSelectedNode.calledBy.slice(0,6)"
                  :key="c.from"
                  class="text-[10px] px-2 py-0.5 rounded bg-neon-blue/10 text-neon-blue border border-neon-blue/20 font-mono"
                >{{ c.from.split(':').pop() }}</span>
                <span v-if="cgSelectedNode.calledBy.length > 6" class="text-[10px] text-gray-500 px-2 py-0.5">+{{ cgSelectedNode.calledBy.length - 6 }} 更多</span>
              </div>
            </div>
          </div>
        </transition>
      </div>
    <!-- State Machine -->
    <div v-show="activeTab === 'statemachine'">
      <div class="glass-card p-6">
        <div v-if="!stateAnalysis || stateMachineModules.length === 0" class="text-gray-500 text-sm py-12 text-center">
          暂无状态流转数据
        </div>
        <template v-else>
          <div class="flex gap-2 mb-5 flex-wrap">
            <button
              v-for="mod in stateMachineModules"
              :key="mod.id"
              @click="selectedStateModule = mod.id"
              class="px-4 py-2 text-sm rounded-lg border transition-all"
              :class="selectedStateModule === mod.id
                ? 'border-transparent text-white'
                : 'border-deep-border text-gray-400 hover:border-gray-500'"
              :style="selectedStateModule === mod.id ? { background: mod.color + '20', borderColor: mod.color + '50' } : {}"
            >
              {{ mod.label }}
            </button>
          </div>

          <div class="relative overflow-auto border border-deep-border rounded-xl bg-deep-card/30" :style="{ maxHeight: '450px' }">
            <svg :viewBox="smViewBox" class="w-full" :style="{ minWidth: smMinWidth + 'px', minHeight: smTotalHeight + 'px' }">
              <defs>
                <marker id="sm-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
                  <path d="M0,0 L10,4 L0,8 Z" fill="#64748b" />
                </marker>
                <marker id="sm-arrow-active" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
                  <path d="M0,0 L10,4 L0,8 Z" fill="#f59e0b" />
                </marker>
                <filter id="sm-glow">
                  <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>

              <g class="sm-edges">
                <g v-for="(edge, idx) in smEdges" :key="'edge-'+idx">
                  <path
                    :d="edge.path"
                    fill="none"
                    :stroke="edge.active ? '#f59e0b' : '#475569'"
                    :stroke-width="edge.active ? 2 : 1.5"
                    :stroke-opacity="edge.active ? 0.9 : 0.5"
                    :marker-end="edge.active ? 'url(#sm-arrow-active)' : 'url(#sm-arrow)'"
                    class="transition-all duration-200 cursor-pointer"
                    @click="selectStateEdge(edge)"
                  />
                  <text
                    v-if="edge.label"
                    :x="edge.labelX"
                    :y="edge.labelY"
                    text-anchor="middle"
                    :fill="edge.active ? '#f59e0b' : '#64748b'"
                    font-size="10"
                    class="pointer-events-none"
                  >
                    <tspan
                      v-for="(line, li) in edge.labelLines"
                      :key="li"
                      :x="edge.labelX"
                      :dy="li === 0 ? 0 : 12"
                    >{{ line }}</tspan>
                  </text>
                </g>
              </g>

              <g class="sm-nodes">
                <g
                  v-for="node in smNodes"
                  :key="node.id"
                  :transform="'translate(' + node.x + ',' + node.y + ')'"
                  class="cursor-pointer transition-all duration-200"
                  @click="selectState(node)"
                >
                  <rect
                    :width="node.width"
                    :height="node.height"
                    :rx="node.height / 2"
                    :fill="selectedState?.id === node.id ? node.color + '30' : (node.color + '15')"
                    :stroke="selectedState?.id === node.id ? '#fff' : (node.color + '80')"
                    :stroke-width="selectedState?.id === node.id ? 2 : 1.5"
                    :filter="selectedState?.id === node.id ? 'url(#sm-glow)' : 'none'"
                    class="transition-all duration-200"
                  />
                  <text
                    :x="node.width / 2"
                    :y="node.height / 2 + 4"
                    text-anchor="middle"
                    fill="#e2e8f0"
                    font-size="12"
                    font-weight="500"
                  >{{ node.label }}</text>
                </g>
              </g>

              <circle v-if="smHasInitial" :cx="smInitialX" :cy="smInitialY" r="6" fill="#10b981">
                <title>初始状态</title>
              </circle>
            </svg>
          </div>

          <div class="flex gap-4 mt-3 text-xs text-gray-400 justify-center flex-wrap">
            <div class="flex items-center gap-1.5">
              <span class="w-3 h-3 rounded-full bg-green-500"></span>
              初始状态
            </div>
            <div class="flex items-center gap-1.5">
              <span class="w-4 h-3 rounded-full border border-gray-500" style="background: rgba(100,116,139,0.2)"></span>
              状态
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-gray-500">→</span>
              状态流转
            </div>
          </div>
        </template>

        <transition name="slide-up">
          <div v-if="selectedState" class="mt-4 glass-card p-5 border border-deep-border">
            <div class="flex items-start justify-between mb-3">
              <div>
                <div class="font-bold text-white">{{ selectedState.label }}</div>
                <div class="text-xs text-gray-500 mt-0.5">{{ currentStateModuleLabel }} 的状态</div>
              </div>
              <button @click="selectedState = null" class="text-gray-500 hover:text-white transition-colors text-lg leading-none">×</button>
            </div>
            <div class="grid grid-cols-2 gap-3 mb-3">
              <div>
                <div class="text-gray-500 text-xs mb-1">进入此状态的方法</div>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="method in selectedState.entryMethods"
                    :key="'in-'+method"
                    class="text-[10px] px-2 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-500/20 font-mono"
                  >{{ method }}</span>
                  <span v-if="!selectedState.entryMethods.length" class="text-xs text-gray-500">无</span>
                </div>
              </div>
              <div>
                <div class="text-gray-500 text-xs mb-1">离开此状态的方法</div>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="method in selectedState.exitMethods"
                    :key="'out-'+method"
                    class="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 font-mono"
                  >{{ method }}</span>
                  <span v-if="!selectedState.exitMethods.length" class="text-xs text-gray-500">无</span>
                </div>
              </div>
            </div>
            <div v-if="selectedState.description" class="text-xs text-gray-400 leading-relaxed">
              {{ selectedState.description }}
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
  </div>
</template>

<!-- Source code viewer modal -->
<SourceViewerModal
  :visible="showSourceViewer"
  :filepath="sourceViewerFilepath"
  :line="sourceViewerLine"
  :end-line="sourceViewerEndLine"
  :hint="sourceViewerHint"
  @close="closeSourceViewer"
/>

<script setup>
import { ref, computed, onMounted } from 'vue'
import SourceViewerModal from './SourceViewerModal.vue'

const props = defineProps({
  deepAnalysis: {
    type: Object,
    default: () => ({})
  }
})

const tabs = [
  { id: 'architecture', label: '模块架构' },
  { id: 'flows', label: '业务流程' },
  { id: 'priority', label: '业务优先级' },
  { id: 'patterns', label: 'Design Patterns' },
  { id: 'key_impls', label: 'Key Impls' },
  { id: 'callgraph', label: '调用图' },
  { id: 'statemachine', label: '状态流转' },
]

const activeTab = ref('architecture')
const selectedNode = ref(null)
const selectedFlowIdx = ref(0)
const selectedPatternIdx = ref(0)
const selectedKeyImplIdx = ref(0)
const Math_round = Math.round

// Source viewer modal
const showSourceViewer = ref(false)
const sourceViewerFilepath = ref('')
const sourceViewerLine = ref(null)
const sourceViewerEndLine = ref(null)
const sourceViewerHint = ref('')

function openSource(filepath, line, endLine, hint) {
  if (!filepath) return
  sourceViewerFilepath.value = filepath
  sourceViewerLine.value = line || null
  sourceViewerEndLine.value = endLine || null
  sourceViewerHint.value = hint || ''
  showSourceViewer.value = true
}

function openSourceFromLocation(location, hint) {
  if (!location) return
  // Parse "filepath:line" format
  const match = location.match(/^(.+?):(\d+)$/)
  if (match) {
    openSource(match[1], parseInt(match[2]), null, hint)
  } else {
    openSource(location, null, null, hint)
  }
}

function closeSourceViewer() {
  showSourceViewer.value = false
}

// Look up filepath from call graph by node_id
function getNodeFilepath(nodeId) {
  const cg = callGraph.value
  if (!cg || !cg.nodes) return ''
  const node = cg.nodes[nodeId]
  return node?.filepath || ''
}

// Open source viewer for a flow step
function openStepSource(step) {
  if (!step) return
  const filepath = getNodeFilepath(step.node_id)
  if (filepath) {
    openSource(filepath, step.line, null, step.method + ' - 流程步骤')
  }
}

// 教师审核模式
const reviewMode = ref(false)
const reviewStatus = ref({})  // { node_id: 'confirmed' | 'rejected' }

// 从 localStorage 恢复审核状态
onMounted(() => {
  const saved = localStorage.getItem('teacher_review_status')
  if (saved) {
    try {
      reviewStatus.value = JSON.parse(saved)
    } catch (e) {
      console.warn('Failed to load review status:', e)
    }
  }
})

function confirmImplementation(nodeId) {
  reviewStatus.value[nodeId] = 'confirmed'
  localStorage.setItem('teacher_review_status', JSON.stringify(reviewStatus.value))
}

function rejectImplementation(nodeId) {
  reviewStatus.value[nodeId] = 'rejected'
  localStorage.setItem('teacher_review_status', JSON.stringify(reviewStatus.value))
}

function clearReview(nodeId) {
  delete reviewStatus.value[nodeId]
  localStorage.setItem('teacher_review_status', JSON.stringify(reviewStatus.value))
}

function getReviewStatus(nodeId) {
  return reviewStatus.value[nodeId] || null
}

// Call graph state
const cgSearch = ref('')
const cgModuleFilter = ref(new Set())
const cgSelectedNode = ref(null)

// Access deep analysis from props
const architecture = computed(() => props.deepAnalysis?.architecture || null)
const flows = computed(() => props.deepAnalysis?.business_flows || [])
const callGraph = computed(() => props.deepAnalysis?.call_graph || null)
const depStrength = computed(() => props.deepAnalysis?.dependency_strength || {})
const businessPriority = computed(() => props.deepAnalysis?.business_priority || null)
const priorityNodes = computed(() => businessPriority.value?.node_scores || [])
const priorityFlows = computed(() => businessPriority.value?.flow_scores || [])
const priorityGaps = computed(() => businessPriority.value?.evidence_gaps || [])

// ---- Call graph: module color map ----
const cgModuleColors = {
  app: '#8b5cf6',
  reservation_manager: '#06b6d4',
  equipment_manager: '#f59e0b',
  safety_checker: '#ec4899',
  user_manager: '#22c55e',
}

const cgModuleShortNames = {
  app: '系统编排',
  reservation_manager: '预约管理',
  equipment_manager: '设备管理',
  safety_checker: '安全检查',
  user_manager: '用户管理',
}

const cgModuleList = computed(() => {
  if (!callGraph.value?.nodes) return []
  const mods = new Set()
  Object.values(callGraph.value.nodes).forEach(n => mods.add(n.module))
  return Array.from(mods).map(id => ({
    id,
    color: cgModuleColors[id] || '#64748b',
    shortName: cgModuleShortNames[id] || id,
  }))
})

// Initialize module filter with all modules selected
onMounted(() => {
  if (cgModuleList.value.length) {
    cgModuleFilter.value = new Set(cgModuleList.value.map(m => m.id))
  }

  // 加载教师审核状态
  const saved = localStorage.getItem('teacher_review_status')
  if (saved) {
    try {
      reviewStatus.value = JSON.parse(saved)
    } catch (e) {
      console.warn('Failed to load review status:', e)
    }
  }
})

function toggleModuleFilter(modId) {
  const next = new Set(cgModuleFilter.value)
  if (next.has(modId)) {
    if (next.size > 1) next.delete(modId)
  } else {
    next.add(modId)
  }
  cgModuleFilter.value = next
}

// ---- Call graph layout (layered / hierarchical) ----
const cgLayoutData = computed(() => {
  if (!callGraph.value?.nodes) return { nodes: [], edges: [], layers: [], totalWidth: 0, totalHeight: 0 }

  const rawNodes = callGraph.value.nodes
  const nodeIds = Object.keys(rawNodes)

  // Build in-degree for layering (longest path from entry)
  const inDegree = {}
  const outEdges = {}
  const inEdges = {}
  nodeIds.forEach(id => {
    inDegree[id] = 0
    outEdges[id] = []
    inEdges[id] = []
  })

  // Collect unique edges
  const edges = []
  const seenEdges = new Set()
  nodeIds.forEach(id => {
    const node = rawNodes[id]
    if (node.calls) {
      node.calls.forEach(call => {
        const key = id + '->' + call.to
        if (seenEdges.has(key)) return
        if (!rawNodes[call.to]) return
        seenEdges.add(key)
        edges.push({ from: id, to: call.to, count: call.count, type: call.type, line: call.line })
        outEdges[id].push(call.to)
        inEdges[call.to].push(id)
        inDegree[call.to] = (inDegree[call.to] || 0) + 1
      })
    }
  })

  // Compute layer assignment using longest-path from entry nodes
  const layers = {}
  const queue = []
  nodeIds.forEach(id => {
    if (rawNodes[id].is_entry_point || inDegree[id] === 0) {
      layers[id] = 0
      queue.push(id)
    }
  })

  // BFS-forward to assign layers
  const visited = new Set()
  let iter = 0
  while (queue.length && iter < 1000) {
    iter++
    const id = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    const myLayer = layers[id] ?? 0
    outEdges[id].forEach(target => {
      if (layers[target] === undefined || layers[target] <= myLayer) {
        layers[target] = myLayer + 1
        if (!visited.has(target)) {
          queue.push(target)
        }
      }
    })
  }

  // Any unvisited nodes (cycles or isolated) go to layer 0
  nodeIds.forEach(id => {
    if (layers[id] === undefined) layers[id] = 0
  })

  // Group nodes by layer
  const layerGroups = {}
  nodeIds.forEach(id => {
    const l = layers[id]
    if (!layerGroups[l]) layerGroups[l] = []
    layerGroups[l].push(id)
  })

  const layerNumbers = Object.keys(layerGroups).map(Number).sort((a, b) => a - b)
  const maxLayer = layerNumbers.length - 1

  // Layout parameters
  const nodeWidth = 160
  const nodeHeight = 40
  const hGap = 80
  const vGap = 12
  const sidePadding = 20
  const topPadding = 40

  // Position nodes within each layer
  const positioned = {}
  let maxHeight = 0

  layerNumbers.forEach((layerNum, colIdx) => {
    const ids = layerGroups[layerNum]
    // Sort by module for visual grouping
    ids.sort((a, b) => {
      const ma = rawNodes[a].module
      const mb = rawNodes[b].module
      if (ma !== mb) return ma.localeCompare(mb)
      return rawNodes[a].name.localeCompare(rawNodes[b].name)
    })

    const colHeight = ids.length * nodeHeight + (ids.length - 1) * vGap
    const startY = topPadding + Math.max(0, (cgTotalHeight - colHeight) / 2)
    // We'll compute totalHeight first, then center

    const x = sidePadding + colIdx * (nodeWidth + hGap)

    ids.forEach((id, rowIdx) => {
      positioned[id] = { x, y: 0 } // y set after height calc
    })
  })

  // Compute per-layer heights, find max
  const layerHeights = {}
  layerNumbers.forEach(layerNum => {
    const ids = layerGroups[layerNum]
    layerHeights[layerNum] = ids.length * nodeHeight + (ids.length - 1) * vGap
  })
  const totalHeight = Math.max(200, Math.max(...Object.values(layerHeights)) + topPadding + 40)

  // Now set Y positions (centered per layer)
  layerNumbers.forEach((layerNum, colIdx) => {
    const ids = layerGroups[layerNum]
    const colH = layerHeights[layerNum]
    const startY = topPadding + (totalHeight - topPadding - 40 - colH) / 2
    ids.forEach((id, rowIdx) => {
      positioned[id].y = startY + rowIdx * (nodeHeight + vGap)
    })
  })

  const totalWidth = sidePadding * 2 + (maxLayer + 1) * nodeWidth + maxLayer * hGap

  // Build enriched node list
  const enrichedNodes = nodeIds.map(id => {
    const n = rawNodes[id]
    const pos = positioned[id]
    const color = cgModuleColors[n.module] || '#64748b'
    return {
      id,
      name: n.name,
      shortName: n.name.length > 18 ? n.name.slice(0, 16) + '…' : n.name,
      module: n.module,
      moduleShort: cgModuleShortNames[n.module] || n.module,
      class: n.class || '',
      isEntry: n.is_entry_point,
      tags: n.tags || [],
      calls: n.calls || [],
      calledBy: n.called_by || [],
      inDegree: (n.called_by || []).length,
      outDegree: (n.calls || []).length,
      lineCount: n.end_line - n.start_line + 1,
      color,
      x: pos.x,
      y: pos.y,
      width: nodeWidth,
      height: nodeHeight,
      layer: layers[id],
    }
  })

  // Build edge paths (bezier)
  const enrichedEdges = edges.map(e => {
    const fromNode = enrichedNodes.find(n => n.id === e.from)
    const toNode = enrichedNodes.find(n => n.id === e.to)
    if (!fromNode || !toNode) return null

    const x1 = fromNode.x + fromNode.width
    const y1 = fromNode.y + fromNode.height / 2
    const x2 = toNode.x
    const y2 = toNode.y + toNode.height / 2

    const dx = x2 - x1
    const cp1x = x1 + dx * 0.5
    const cp2x = x2 - dx * 0.5
    const path = `M ${x1} ${y1} C ${cp1x} ${y1}, ${cp2x} ${y2}, ${x2} ${y2}`

    return { ...e, path, fromNode: e.from, toNode: e.to, highlighted: false }
  }).filter(Boolean)

  // Build layer info
  const layerInfo = layerNumbers.map((num, idx) => ({
    num,
    label: num === 0 ? '入口层' : (num === layerNumbers[layerNumbers.length - 1] ? '叶子层' : `第 ${num} 层`),
    x: sidePadding + idx * (nodeWidth + hGap),
    width: nodeWidth,
  }))

  return {
    allNodes: enrichedNodes,
    allEdges: enrichedEdges,
    layers: layerInfo,
    totalWidth,
    totalHeight,
  }
})

const cgTotalWidth = computed(() => cgLayoutData.value.totalWidth || 800)
const cgTotalHeight = computed(() => cgLayoutData.value.totalHeight || 400)
const cgMinWidth = computed(() => Math.max(600, cgTotalWidth.value))
const cgViewBox = computed(() => `0 0 ${cgTotalWidth.value} ${cgTotalHeight.value}`)
const cgLayers = computed(() => cgLayoutData.value.layers || [])

// Filter nodes by module filter and search
const cgVisibleNodeIds = computed(() => {
  const search = cgSearch.value.toLowerCase().trim()
  return cgLayoutData.value.allNodes
    .filter(n => cgModuleFilter.value.has(n.module))
    .filter(n => !search || n.name.toLowerCase().includes(search) || n.class?.toLowerCase().includes(search))
    .map(n => n.id)
})

const cgVisibleNodes = computed(() => {
  const ids = new Set(cgVisibleNodeIds.value)
  return cgLayoutData.value.allNodes.filter(n => ids.has(n.id))
})

const cgVisibleEdges = computed(() => {
  const ids = new Set(cgVisibleNodeIds.value)
  const selected = cgSelectedNode.value?.id
  return cgLayoutData.value.allEdges
    .filter(e => ids.has(e.from) && ids.has(e.to))
    .map(e => ({
      ...e,
      highlighted: !!selected && (e.from === selected || e.to === selected),
    }))
})

function selectCgNode(node) {
  cgSelectedNode.value = cgSelectedNode.value?.id === node.id ? null : node
}

const designPatterns = computed(() => props.deepAnalysis?.design_patterns?.patterns || [])
const selectedPattern = computed(() => designPatterns.value[selectedPatternIdx.value] || null)
const keyImplementations = computed(() => props.deepAnalysis?.key_implementations?.implementations || [])
const selectedKeyImpl = computed(() => keyImplementations.value[selectedKeyImplIdx.value] || null)
const selectedFlow = computed(() => flows.value[selectedFlowIdx.value] || null)

// Architecture layout with computed edges
const archNodes = computed(() => {
  if (!architecture.value?.nodes) return []
  return Object.values(architecture.value.nodes)
})

const archHeight = computed(() => {
  if (!architecture.value?.layout) return 300
  return architecture.value.layout.total_height || 300
})

const archViewBox = computed(() => {
  const layout = architecture.value?.layout
  if (!layout) return '0 0 800 300'
  const w = layout.total_width || 800
  const h = layout.total_height || 300
  return `0 0 ${w} ${h}`
})

const archEdges = computed(() => {
  if (!architecture.value?.edges || !architecture.value?.nodes) return []
  const nodes = architecture.value.nodes

  return architecture.value.edges.map(edge => {
    const from = nodes[edge.from]
    const to = nodes[edge.to]
    if (!from || !to) return null

    // Calculate bezier path between module boxes
    const x1 = from.x + from.width / 2
    const y1 = from.y + from.height
    const x2 = to.x + to.width / 2
    const y2 = to.y

    const midY = (y1 + y2) / 2
    const path = `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`

    // Color based on edge type
    let color = '#64748b'
    let width = 1.5
    if (edge.type === 'orchestration') {
      color = '#a78bfa'
      width = 2
    } else if (edge.strength >= 0.5) {
      color = '#06b6d4'
      width = 2
    }

    return { path, color, width }
  }).filter(Boolean)
})

function nodeColor(layer) {
  const colors = {
    orchestration: '#8b5cf6',
    business: '#06b6d4',
    support: '#10b981',
    infrastructure: '#f59e0b',
  }
  return colors[layer] || '#64748b'
}

function roleBadgeClass(role) {
  const classes = {
    orchestrator: 'bg-purple-500/20 text-purple-300 border border-purple-500/30',
    core: 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30',
    intermediate: 'bg-blue-500/20 text-blue-300 border border-blue-500/30',
    peripheral: 'bg-gray-500/20 text-gray-300 border border-gray-500/30',
  }
  return classes[role] || 'bg-gray-500/20 text-gray-300'
}

function roleLabel(role) {
  const labels = {
    orchestrator: '编排器',
    core: '核心模块',
    intermediate: '中间模块',
    peripheral: '边缘模块',
  }
  return labels[role] || role
}

function moduleDeps(moduleId) {
  const mods = depStrength.value.modules || {}
  const mod = mods[moduleId]
  if (!mod) return null
  return {
    out: mod.fan_out || 0,
    in: mod.fan_in || 0,
  }
}

function selectNode(node) {
  selectedNode.value = selectedNode.value?.module_id === node.module_id ? null : node
}

function stepDotClass(step) {
  if (step.is_state_change) return 'border-amber-400 bg-amber-400'
  if (step.is_validation) return 'border-green-400 bg-green-400'
  if (step.is_module_boundary) return 'border-neon-purple bg-neon-purple'
  return 'border-gray-500 bg-gray-700'
}

// ---- State Machine View ----
const stateAnalysis = computed(() => props.deepAnalysis?.state_analysis || null)

const stateModuleColors = {
  reservation_manager: '#06b6d4',
  equipment_manager: '#f59e0b',
  safety_checker: '#ec4899',
  user_manager: '#22c55e',
}

const stateModuleLabels = {
  reservation_manager: '预约状态',
  equipment_manager: '设备状态',
  safety_checker: '隐患状态',
  user_manager: '用户状态',
}

const stateMachineModules = computed(() => {
  if (!stateAnalysis.value) return []
  const result = []
  Object.keys(stateAnalysis.value).forEach(key => {
    const cls = stateAnalysis.value[key]
    if (cls.class_constants && cls.class_constants.length > 0) {
      // 只显示有 STATUS 常量的模块（有明确状态机）
      const statusConstants = cls.class_constants.filter(c => c.startsWith('STATUS_'))
      if (statusConstants.length > 1) {
        const modId = cls.module
        result.push({
          id: modId,
          label: stateModuleLabels[modId] || modId,
          color: stateModuleColors[modId] || '#64748b',
          classKey: key,
        })
      }
    }
  })
  return result
})

const selectedStateModule = ref('')
const selectedState = ref(null)
const selectedStateEdge = ref(null)

// Initialize first module
onMounted(() => {
  if (stateMachineModules.value.length > 0 && !selectedStateModule.value) {
    selectedStateModule.value = stateMachineModules.value[0].id
  }
})

const currentStateModuleLabel = computed(() => {
  const mod = stateMachineModules.value.find(m => m.id === selectedStateModule.value)
  return mod?.label || ''
})

// Extract state machine data for selected module
const currentStateData = computed(() => {
  if (!stateAnalysis.value || !selectedStateModule.value) return null
  const modKey = Object.keys(stateAnalysis.value).find(key =>
    stateAnalysis.value[key].module === selectedStateModule.value
  )
  return modKey ? stateAnalysis.value[modKey] : null
})

// Build state list from STATUS_* constants and method state transitions
const smStates = computed(() => {
  const data = currentStateData.value
  if (!data) return []

  const statusConstants = (data.class_constants || []).filter(c => c.startsWith('STATUS_'))
  if (statusConstants.length === 0) return []

  const mod = stateMachineModules.value.find(m => m.id === selectedStateModule.value)
  const color = mod?.color || '#64748b'

  // State name mapping: STATUS_PENDING -> "待审批"
  const nameMap = {
    STATUS_PENDING: '待审批',
    STATUS_APPROVED: '已通过',
    STATUS_REJECTED: '已拒绝',
    STATUS_CANCELLED: '已取消',
    STATUS_COMPLETED: '已完成',
    STATUS_AVAILABLE: '可用',
    STATUS_BORROWED: '借出中',
    STATUS_MAINTENANCE: '维护中',
    STATUS_SCRAPPED: '已报废',
    STATUS_OPEN: '待处理',
    STATUS_IN_PROGRESS: '整改中',
    STATUS_CLOSED: '已关闭',
  }

  // Identify which methods write state (dict values)
  const methodDictWrites = data.method_dict_writes || {}
  const stateWriteMethods = {}  // stateValue -> [methods that set it]
  const stateReadMethods = {}

  // For now, build states from constants
  return statusConstants.map((constant, idx) => {
    const shortName = constant.replace('STATUS_', '')
    return {
      id: constant,
      label: nameMap[constant] || shortName,
      constant,
      shortName,
      color,
      idx,
      entryMethods: [],
      exitMethods: [],
      description: '',
    }
  })
})

// State transitions: inferred from method names and state patterns
const smTransitions = computed(() => {
  const states = smStates.value
  if (states.length < 2) return []

  const data = currentStateData.value
  const modId = selectedStateModule.value

  // Heuristic transitions based on common state machine patterns
  const patternTransitions = {
    reservation_manager: [
      { from: 'STATUS_PENDING', to: 'STATUS_APPROVED', label: 'approve' },
      { from: 'STATUS_PENDING', to: 'STATUS_REJECTED', label: 'reject' },
      { from: 'STATUS_PENDING', to: 'STATUS_CANCELLED', label: 'cancel' },
      { from: 'STATUS_APPROVED', to: 'STATUS_COMPLETED', label: 'complete' },
      { from: 'STATUS_APPROVED', to: 'STATUS_CANCELLED', label: 'cancel' },
    ],
    equipment_manager: [
      { from: 'STATUS_AVAILABLE', to: 'STATUS_BORROWED', label: 'borrow' },
      { from: 'STATUS_BORROWED', to: 'STATUS_AVAILABLE', label: 'return' },
      { from: 'STATUS_AVAILABLE', to: 'STATUS_MAINTENANCE', label: 'maintain' },
      { from: 'STATUS_MAINTENANCE', to: 'STATUS_AVAILABLE', label: 'complete' },
      { from: 'STATUS_AVAILABLE', to: 'STATUS_SCRAPPED', label: 'scrap' },
    ],
    safety_checker: [
      { from: 'STATUS_OPEN', to: 'STATUS_IN_PROGRESS', label: 'assign' },
      { from: 'STATUS_IN_PROGRESS', to: 'STATUS_CLOSED', label: 'close' },
      { from: 'STATUS_OPEN', to: 'STATUS_CLOSED', label: 'close' },
    ],
  }

  const transitions = patternTransitions[modId] || []
  // Find actual methods that correspond to each transition
  const methods = Object.keys(data?.method_writes || {})

  return transitions.map(t => {
    const matchedMethod = methods.find(m => {
      const ml = m.toLowerCase()
      const label = t.label.toLowerCase()
      return ml.includes(label) || label.includes(ml)
    })
    return {
      ...t,
      method: matchedMethod || t.label,
    }
  })
})

// Layout state nodes in a horizontal line / circle
const smLayout = computed(() => {
  const states = smStates.value
  const transitions = smTransitions.value
  if (states.length === 0) return { nodes: [], edges: [], totalWidth: 400, totalHeight: 200, hasInitial: false, initialX: 0, initialY: 0 }

  const nodeWidth = 120
  const nodeHeight = 40
  const hGap = 50
  const padding = 40
  const totalWidth = padding * 2 + states.length * nodeWidth + (states.length - 1) * hGap
  const totalHeight = 240

  // Horizontal layout, 2 rows if more than 4 states
  const perRow = states.length <= 4 ? states.length : Math.ceil(states.length / 2)
  const rowGap = 90
  const rows = Math.ceil(states.length / perRow)
  const actualWidth = padding * 2 + perRow * nodeWidth + (perRow - 1) * hGap
  const actualHeight = 120 + rows * (nodeHeight + rowGap)

  const nodes = states.map((state, idx) => {
    const row = Math.floor(idx / perRow)
    const col = idx % perRow
    const rowCount = row < rows - 1 ? perRow : (states.length - row * perRow)
    const rowWidth = rowCount * nodeWidth + (rowCount - 1) * hGap
    const rowStartX = padding + (actualWidth - padding * 2 - rowWidth) / 2
    const x = rowStartX + col * (nodeWidth + hGap)
    const y = 80 + row * (nodeHeight + rowGap)
    return { ...state, x, y, width: nodeWidth, height: nodeHeight }
  })

  // Build edges
  const nodeMap = {}
  nodes.forEach(n => { nodeMap[n.id] = n })

  const edges = transitions.map(t => {
    const from = nodeMap[t.from]
    const to = nodeMap[t.to]
    if (!from || !to) return null

    // Determine if forward or backward
    const isForward = to.x > from.x
    const isSameRow = Math.abs(from.y - to.y) < 10

    let path = ''
    let labelX = 0
    let labelY = 0

    if (isSameRow) {
      // Horizontal edge
      const x1 = from.x + from.width
      const y1 = from.y + from.height / 2
      const x2 = to.x
      const y2 = to.y + to.height / 2
      const midX = (x1 + x2) / 2
      path = `M ${x1} ${y1} L ${x2} ${y2}`
      labelX = midX
      labelY = y1 - 8
    } else if (!isSameRow) {
      // Curved edge between rows
      const x1 = from.x + from.width / 2
      const y1 = from.y + from.height
      const x2 = to.x + to.width / 2
      const y2 = to.y
      const midY = (y1 + y2) / 2
      const dx = x2 - x1
      const curveOffset = Math.sign(dx) * 30
      path = `M ${x1} ${y1} C ${x1 + curveOffset} ${midY}, ${x2 - curveOffset} ${midY}, ${x2} ${y2}`
      labelX = (x1 + x2) / 2 + (dx > 0 ? 15 : -15)
      labelY = midY
    }

    // Split label into lines
    const labelLines = t.method ? [t.method + '()'] : []

    return {
      from: t.from,
      to: t.to,
      method: t.method,
      path,
      label: t.method,
      labelLines,
      labelX,
      labelY,
      active: false,
    }
  }).filter(Boolean)

  // Initial state: first status is usually the initial state
  const firstNode = nodes[0]
  const hasInitial = true
  const initialX = firstNode.x - 30
  const initialY = firstNode.y + firstNode.height / 2

  // Add initial -> first state edge
  if (firstNode) {
    const initPath = `M ${initialX + 6} ${initialY} L ${firstNode.x} ${firstNode.y + firstNode.height / 2}`
    edges.unshift({
      from: '__initial__',
      to: firstNode.id,
      method: 'create',
      path: initPath,
      label: '',
      labelLines: [],
      labelX: 0,
      labelY: 0,
      active: false,
      isInitial: true,
    })
  }

  return {
    nodes,
    edges,
    totalWidth: actualWidth,
    totalHeight: actualHeight,
    hasInitial,
    initialX,
    initialY,
  }
})

const smNodes = computed(() => smLayout.value.nodes)
const smEdges = computed(() => {
  const sel = selectedState.value?.id
  return smLayout.value.edges.map(e => ({
    ...e,
    active: !!sel && (e.from === sel || e.to === sel),
  }))
})
const smTotalWidth = computed(() => smLayout.value.totalWidth || 400)
const smTotalHeight = computed(() => smLayout.value.totalHeight || 200)
const smMinWidth = computed(() => Math.max(400, smTotalWidth.value))
const smViewBox = computed(() => `0 0 ${smTotalWidth.value} ${smTotalHeight.value}`)
const smHasInitial = computed(() => smLayout.value.hasInitial)
const smInitialX = computed(() => smLayout.value.initialX)
const smInitialY = computed(() => smLayout.value.initialY)

function selectState(node) {
  selectedState.value = selectedState.value?.id === node.id ? null : node
}

function selectStateEdge(edge) {
  // Highlight both connected states
  if (edge.from && edge.from !== '__initial__') {
    const fromNode = smNodes.value.find(n => n.id === edge.from)
    if (fromNode) {
      selectedState.value = fromNode
      return
    }
  }
  if (edge.to) {
    const toNode = smNodes.value.find(n => n.id === edge.to)
    if (toNode) {
      selectedState.value = toNode
    }
  }
}
</script>

<style scoped>
.tab-btn {
  @apply px-4 py-2 text-sm rounded-lg border border-deep-border text-gray-400 transition-all;
}
.tab-btn:hover {
  @apply border-neon-blue/40 text-white;
}
.tab-btn.active {
  @apply border-neon-blue bg-neon-blue/10 text-neon-blue;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}
.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.flow-steps::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 8px;
  bottom: 8px;
  width: 1px;
  background: linear-gradient(to bottom, #334155, #1e293b);
}
</style>
