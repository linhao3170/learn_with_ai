<template>
  <div class="stage-design">
    <!-- ================= 页头 ================= -->
    <div class="glass-card p-6 mb-5" data-test="stage-design-view">
      <div class="flex items-center gap-2 flex-wrap mb-1">
        <h2 class="text-lg font-bold text-white">阶段四 · 设计画布</h2>
        <span class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-blue/10 text-neon-blue border-neon-blue/30">
          design_canvas
        </span>
        <span v-if="task" class="text-[10px] font-mono text-gray-600">{{ task.algorithm_version }}</span>
      </div>
      <p class="text-xs text-gray-400 leading-relaxed">
        系统给你一个<strong class="text-gray-200">新需求</strong>，模块由你自己拆、自己画、自己说明理由。
        评审在后端按<strong class="text-gray-200">六维结构信号</strong>进行
        （<span class="font-mono">engine/design/rubric.py</span>），**算不出来的维度会如实显示「本轮未评估」，不会填 0**；
        每一条反馈都能追溯到触发它的信号码。
      </p>
    </div>

    <!-- 加载 / 错误 / 离线 -->
    <div v-if="loading" class="glass-card p-10 text-center text-gray-400 text-sm">正在加载设计任务…</div>
    <div v-else-if="loadError" class="glass-card p-10 text-center" data-test="design-load-error">
      <div class="text-red-400 text-sm mb-2">无法加载设计任务</div>
      <div class="text-xs text-gray-500 font-mono break-all">{{ loadError }}</div>
    </div>

    <template v-else-if="task">
      <!-- ================= ① 题干与需求简报（学生视图，绝不含必备能力清单） ================= -->
      <section class="glass-card p-6 mb-5" data-test="design-task">
        <div class="flex items-center gap-2 flex-wrap mb-2">
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-neon-purple/10 text-neon-purple border-neon-purple/30"
                data-test="design-task-level">
            {{ task.level }}{{ task.level_label ? ' · ' + task.level_label : '' }}
          </span>
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-deep-card text-gray-300 border-deep-border"
                data-test="design-task-type">
            {{ task.type_name_cn }}
          </span>
          <span
            v-if="task.needs_review"
            class="text-[10px] px-1.5 py-0.5 rounded border bg-amber-500/10 text-amber-400 border-amber-500/30"
            data-test="design-needs-review"
          >
            必备能力清单待教师确认（{{ task.must_have_source }}）
          </span>
          <span class="text-[10px] text-gray-500 ml-auto">本次有 {{ task.must_have_count }} 项必备能力（清单不下发）</span>
        </div>

        <!-- 任务切换：换一道题就换一套口径，所以切题时清空画布结论 -->
        <div v-if="taskList.length > 1" class="mb-3 flex items-center gap-2 flex-wrap">
          <label class="text-[11px] text-gray-500">选一道题：</label>
          <select
            v-model="currentTaskId"
            class="bg-deep-card border border-deep-border rounded-lg px-2 py-1 text-xs text-gray-200"
            data-test="design-task-select"
          >
            <option v-for="item in taskList" :key="item.task_id" :value="item.task_id">
              {{ item.type_name_cn }}（{{ item.task_id }}）
            </option>
          </select>
          <span class="text-[11px] text-gray-600">换题会重置画布结论（作答内容保留在本地草稿）</span>
        </div>

        <div class="text-sm text-gray-200 leading-relaxed mb-3" data-test="design-task-prompt">
          {{ task.prompt_cn }}
        </div>
        <div class="text-xs text-gray-400 leading-relaxed mb-3">{{ task.scenario_cn }}</div>
        <div class="text-xs text-gray-300 leading-relaxed p-3 rounded-xl bg-deep-card/60 border border-deep-border"
             data-test="design-brief">
          <div class="text-[10px] text-gray-500 mb-1">需求简报（{{ briefModeLabel }}）</div>
          {{ task.brief?.text_cn }}
        </div>
        <div v-if="task.brief?.items?.length" class="mt-2 flex gap-1.5 flex-wrap">
          <span
            v-for="(item, i) in task.brief.items"
            :key="i"
            class="text-[10px] px-1.5 py-0.5 rounded border bg-deep-card text-gray-300 border-deep-border"
            data-test="design-brief-item"
          >{{ item }}</span>
        </div>
      </section>

      <!-- ================= ② 画布 + 卡片编辑面板 ================= -->
      <div class="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-5">
        <section class="xl:col-span-2 glass-card p-4">
          <div class="flex items-center gap-2 flex-wrap mb-3">
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-gradient-to-r from-neon-blue to-neon-purple"
              data-test="design-add-module"
              @click="addModule()"
            >添加模块</button>
            <button
              class="px-3 py-1.5 rounded-lg text-xs text-gray-300 border border-deep-border hover:border-neon-blue/40 disabled:opacity-40"
              data-test="design-remove-selected"
              :disabled="!selection"
              @click="removeSelection()"
            >删除选中{{ selectionLabel }}</button>
            <span class="text-[11px] text-gray-500">
              {{ nodes.length }} 个模块 · {{ edges.length }} 条依赖
            </span>
            <span class="text-[11px] text-gray-600">
              双击空白处加模块；拖动节点移动；从节点右侧圆点拖到另一个节点建立依赖；点击连线可选中删除
            </span>
          </div>

          <!--
            画布：原生 HTML5 拖拽 + 手写 SVG 连线（README §12.4 的首选方案，不引第三方图库）。
            节点坐标直接存在数据里，连线路径由坐标算出来 —— 所以不依赖 DOM 测量，
            在 jsdom 走查里也能被断言（浏览器里同样正确）。
          -->
          <div
            ref="canvasEl"
            class="relative w-full rounded-xl border border-deep-border bg-deep-card/40 overflow-hidden"
            style="height: 460px"
            data-test="design-canvas"
            @dblclick="onCanvasDblClick"
            @mouseup="onCanvasMouseUp"
            @mousemove="onCanvasMouseMove"
          >
            <svg class="absolute inset-0 w-full h-full" style="pointer-events: none" data-test="design-edge-layer">
              <defs>
                <marker id="lwai-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                </marker>
                <marker id="lwai-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
                </marker>
              </defs>
              <g v-for="edge in edges" :key="edge.from + '->' + edge.to">
                <path
                  :d="edgePath(edge)"
                  fill="none"
                  :stroke="isEdgeSelected(edge) ? '#38bdf8' : '#64748b'"
                  :stroke-width="isEdgeSelected(edge) ? 2.5 : 1.6"
                  :marker-end="isEdgeSelected(edge) ? 'url(#lwai-arrow-active)' : 'url(#lwai-arrow)'"
                  style="pointer-events: stroke; cursor: pointer"
                  :data-test="'design-edge'"
                  :data-edge-from="edge.from"
                  :data-edge-to="edge.to"
                  @click.stop="selectEdge(edge)"
                />
              </g>
              <path
                v-if="linkDraft"
                :d="linkDraftPath"
                fill="none"
                stroke="#38bdf8"
                stroke-width="2"
                stroke-dasharray="5 4"
                data-test="design-link-draft"
              />
            </svg>

            <div
              v-for="node in nodes"
              :key="node.id"
              class="absolute select-none rounded-xl border bg-deep-card shadow-lg"
              :class="isNodeSelected(node) ? 'border-neon-blue' : 'border-deep-border'"
              :style="{ left: node.x + 'px', top: node.y + 'px', width: NODE_W + 'px' }"
              :data-test="'design-node'"
              :data-module-id="node.id"
              :data-module-name="node.name"
              @mousedown="startDrag(node, $event)"
              @mouseup="finishLink(node, $event)"
              @click.stop="selectNode(node)"
            >
              <div class="flex items-center gap-1 px-2 py-1.5 border-b border-deep-border">
                <span class="text-[10px] font-mono text-gray-500">{{ node.id }}</span>
                <input
                  v-model="node.name"
                  class="flex-1 min-w-0 bg-transparent text-xs text-white outline-none border-b border-transparent focus:border-neon-blue/50"
                  :data-test="'design-node-name'"
                  placeholder="模块名（双击可直接改）"
                  @mousedown.stop
                  @change="markDirty"
                />
                <button
                  class="text-[10px] text-gray-500 hover:text-red-400 px-1"
                  :data-test="'design-node-delete'"
                  title="删除模块"
                  @click.stop="removeNode(node)"
                >✕</button>
              </div>
              <div class="px-2 py-1.5">
                <div class="text-[10px] text-gray-400 truncate">
                  {{ node.objective || '（还没写模块目标）' }}
                </div>
                <div class="text-[9px] text-gray-600 mt-1">
                  {{ node.parent_id ? '父模块 ' + node.parent_id : '一级模块' }}
                  · {{ (node.depends_on || []).length }} 条声明依赖
                </div>
              </div>
              <!-- 连线起点：从这里拖到另一个节点 -->
              <div
                class="absolute -right-2 top-1/2 -mt-2 w-4 h-4 rounded-full bg-neon-blue/30 border border-neon-blue cursor-crosshair"
                :data-test="'design-port-out'"
                :data-module-id="node.id"
                @mousedown.stop="startLink(node, $event)"
              ></div>
            </div>

            <div v-if="!nodes.length" class="absolute inset-0 flex items-center justify-center text-xs text-gray-500">
              画布是空的：点「添加模块」或双击空白处开始设计（评审要求至少有一个模块）
            </div>
          </div>

          <!-- 设计理由：第 6 维只衡量「可核查性」，所以这里要说清为什么这样拆 -->
          <div class="mt-4">
            <div class="text-[11px] text-gray-400 mb-1">
              设计理由（第 6 维按「可核查性」评审：引用的模块名必须真的在图上、要引用规则或状态）
            </div>
            <textarea
              v-model="rationale"
              rows="3"
              class="w-full bg-deep-card border border-deep-border rounded-xl px-3 py-2 text-xs text-gray-200
                     leading-relaxed focus:outline-none focus:border-neon-blue/50 resize-y"
              data-test="design-rationale"
              placeholder="例如：我把「审批」独立成模块，因为它和「申请」是两个角色的职责；两条依赖是……"
              @change="markDirty"
            ></textarea>
          </div>

          <div class="flex items-center gap-3 mt-3 flex-wrap">
            <button
              class="px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all bg-gradient-to-r from-neon-blue to-neon-purple
                     disabled:opacity-40 disabled:cursor-not-allowed"
              data-test="design-submit"
              :disabled="!canSubmit"
              @click="submit"
            >
              {{ submitting ? '正在评审…' : (history.length ? '再次提交（第 ' + (history.length + 1) + ' 次）' : '提交设计，看六维评审') }}
            </button>
            <span class="text-[11px] text-gray-500">
              {{ nodes.length }} 个模块 · {{ edges.length }} 条依赖 · 理由 {{ rationale.trim().length }} 字
            </span>
            <span v-if="submitError" class="text-[11px] text-amber-400" data-test="design-submit-error">
              {{ submitError }}
            </span>
            <span class="text-[11px] text-gray-600 ml-auto">画布草稿只存在本机浏览器，刷新后保留</span>
          </div>
        </section>

        <!-- 右侧：选中模块的卡片编辑面板 -->
        <section class="glass-card p-4" data-test="design-card-panel">
          <div class="text-xs font-bold text-white mb-3">
            模块卡片{{ selectedNode ? '· ' + (selectedNode.name || selectedNode.id) : '' }}
          </div>
          <div v-if="!selectedNode" class="text-[11px] text-gray-500 leading-relaxed">
            在画布上点一个模块，就能在这里填写它的卡片字段。
            第 2 维「职责清晰度」会看「不负责什么」是否填了，第 5 维「异常与边界」会看异常分支。
          </div>
          <template v-else>
            <label class="block text-[11px] text-gray-500 mb-1">模块目标</label>
            <input
              v-model="selectedNode.objective"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-objective"
              placeholder="它解决什么问题"
              @change="markDirty"
            />
            <label class="block text-[11px] text-gray-500 mb-1">不负责什么（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.does_not)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-does-not"
              placeholder="例如：不负责设备状态"
              @input="setLines(selectedNode, 'does_not', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">输入（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.inputs)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-inputs"
              @input="setLines(selectedNode, 'inputs', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">输出（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.outputs)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-outputs"
              @input="setLines(selectedNode, 'outputs', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">状态变化（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.state_changes)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-state-changes"
              @input="setLines(selectedNode, 'state_changes', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">业务规则（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.business_rules)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-rules"
              @input="setLines(selectedNode, 'business_rules', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">异常情况（每行一条）</label>
            <textarea
              :value="linesToText(selectedNode.exceptions)"
              rows="2"
              class="w-full mb-3 bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-exceptions"
              @input="setLines(selectedNode, 'exceptions', $event)"
            ></textarea>
            <label class="block text-[11px] text-gray-500 mb-1">父模块（层级归属，用于第 3 维）</label>
            <select
              v-model="selectedNode.parent_id"
              class="w-full bg-deep-card border border-deep-border rounded-lg px-2 py-1.5 text-xs text-gray-200"
              data-test="design-card-parent"
              @change="markDirty"
            >
              <option :value="null">（一级模块）</option>
              <option v-for="other in otherNodes(selectedNode)" :key="other.id" :value="other.id">
                {{ other.id }} · {{ other.name }}
              </option>
            </select>
          </template>
        </section>
      </div>

      <!-- ================= ③ 提交后才渲染的六维评审（提交前这里一个节点都没有） ================= -->
      <section v-if="report" class="glass-card p-6" data-test="design-report">
        <div class="flex items-center gap-2 flex-wrap mb-1">
          <h3 class="text-base font-bold text-white">六维评审</h3>
          <span class="text-[10px] px-1.5 py-0.5 rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
            {{ report.scoring }}
          </span>
          <span class="text-[10px] font-mono text-gray-600">{{ report.algorithm_version }}</span>
          <span class="text-[10px] text-gray-500 ml-auto" data-test="design-iteration">
            第 {{ report.iteration }} 次提交
          </span>
        </div>

        <!-- 总分与权重重归一化说明：算不出来的维度不参与，也不按 0 算 -->
        <div class="p-4 rounded-xl bg-deep-card/60 border border-deep-border mb-4" data-test="design-overall">
          <div class="flex items-baseline gap-3 flex-wrap">
            <span class="text-3xl font-bold text-white" data-test="design-overall-score">
              {{ report.overall_score === null ? '—' : report.overall_score }}
            </span>
            <span class="text-[11px] text-gray-400">
              本轮评估覆盖 {{ report.evaluated_dimensions }}/{{ report.total_dimensions }} 维
              <span v-if="report.weights_renormalized">（权重已按比例归一化）</span>
            </span>
          </div>
          <p class="text-[11px] text-gray-400 mt-2 leading-relaxed">{{ report.overall_note }}</p>
          <p class="text-[11px] text-gray-500 mt-2 leading-relaxed" data-test="design-no-fake-score">
            本页只显示引擎真正算出来的东西：<strong class="text-gray-300">算不出来的维度显示「本轮未评估」与原因，不填 0</strong>。
            分数不是对业务能力的结论 —— 规则引擎判事实，教师判语义。
          </p>
        </div>

        <!-- 与上一轮的对比（第 2 次提交起） -->
        <div v-if="comparison" class="p-3 rounded-xl bg-deep-card/40 border border-deep-border mb-4" data-test="design-compare">
          <div class="text-[11px] text-gray-400 leading-relaxed">{{ comparison }}</div>
        </div>

        <!-- 六个维度 -->
        <div class="space-y-3">
          <div
            v-for="dim in report.dimensions"
            :key="dim.key"
            class="rounded-xl border p-4"
            :class="dim.status === 'evaluated' ? 'border-deep-border bg-deep-card/40' : 'border-dashed border-slate-500/40 bg-deep-card/20'"
            data-test="design-dimension"
            :data-dimension-key="dim.key"
            :data-status="dim.status"
          >
            <div class="flex items-center gap-2 flex-wrap mb-1">
              <span class="text-sm text-white font-medium">{{ dim.name }}</span>
              <span
                class="text-[10px] px-1.5 py-0.5 rounded border"
                :class="dim.status === 'evaluated'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-slate-500/10 text-slate-300 border-slate-500/40'"
                :data-test="dim.status === 'evaluated' ? 'design-dimension-score' : 'design-not-evaluated'"
              >
                {{ dim.status === 'evaluated' ? ('得分 ' + dim.score) : '本轮未评估' }}
              </span>
              <span class="text-[10px] text-gray-500 font-mono">
                权重 {{ dim.weight }}{{ normalizedWeight(dim.key) !== null ? '（归一化后 ' + normalizedWeight(dim.key) + '）' : '' }}
              </span>
              <span v-if="dim.not_filled" class="text-[10px] px-1.5 py-0.5 rounded border bg-amber-500/10 text-amber-400 border-amber-500/30">
                not_filled
              </span>
            </div>
            <div v-if="dim.status !== 'evaluated'" class="text-[11px] text-gray-400 leading-relaxed mb-2" data-test="design-not-evaluated-reason">
              未参与评分：{{ dim.reason }}
            </div>
            <ul class="space-y-1 mb-2">
              <li v-for="(line, i) in dim.findings" :key="'f' + i" class="text-[11px] text-gray-300 leading-relaxed flex gap-2">
                <span class="text-gray-600">·</span><span>{{ line }}</span>
              </li>
            </ul>
            <div v-if="dim.issues?.length" class="mt-2 pt-2 border-t border-deep-border">
              <div class="text-[10px] text-amber-400 mb-1">系统指出的问题（每条都能追溯到右侧信号码）</div>
              <ul class="space-y-1">
                <li v-for="(line, i) in dim.issues" :key="'i' + i" class="text-[11px] text-amber-200/90 leading-relaxed flex gap-2">
                  <span class="text-amber-500/70">·</span><span>{{ line }}</span>
                </li>
              </ul>
            </div>
            <div v-if="dim.signals?.length" class="mt-2 flex gap-1.5 flex-wrap" data-test="design-signals">
              <span
                v-for="(sig, i) in dim.signals"
                :key="'s' + i"
                class="text-[10px] font-mono px-1.5 py-0.5 rounded border bg-deep-card text-gray-400 border-deep-border"
                :data-test="'design-signal'"
                :data-signal-code="sig.code"
              >{{ sig.code }}{{ sig.penalty ? ' −' + sig.penalty : '' }}</span>
            </div>
          </div>
        </div>

        <!-- 匹配三分类：先给「你提到了什么」，再给「还没有识别到什么」 -->
        <div class="mt-5 pt-4 border-t border-deep-border" data-test="design-matching">
          <div class="text-xs font-bold text-white mb-2">必备能力的三分类清单</div>
          <p class="text-[11px] text-gray-500 mb-3 leading-relaxed">
            「未识别」和「未覆盖」是两件事：前者是「你画了、但系统没能把它和必备能力对上」（可能是命名不同，不计入覆盖度），
            后者才是必备能力没有承担者。词汇匹配必然有假阴性，所以下面的措辞是「未在设计中识别到」，不是「你漏了」。
          </p>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <div class="text-[11px] text-emerald-400 mb-1">已识别（{{ report.matching.counts.matched }}）</div>
              <div v-for="item in report.matching.matched" :key="item.key"
                   class="text-[11px] text-gray-300 px-2 py-1 rounded border border-emerald-500/25 bg-emerald-500/5 mb-1"
                   data-test="design-matched">
                {{ item.name_cn }}
              </div>
            </div>
            <div>
              <div class="text-[11px] text-amber-400 mb-1">未识别到承担者（{{ report.matching.counts.missing }}）</div>
              <div v-for="item in report.matching.missing" :key="item.key"
                   class="text-[11px] text-gray-300 px-2 py-1 rounded border border-amber-500/25 bg-amber-500/5 mb-1"
                   data-test="design-missing">
                {{ item.name_cn }}
              </div>
            </div>
            <div>
              <div class="text-[11px] text-slate-300 mb-1">系统未能识别的模块（{{ report.matching.counts.unrecognized_modules }}）</div>
              <div v-for="item in report.matching.unrecognized_modules" :key="item.module_id"
                   class="text-[11px] text-gray-300 px-2 py-1 rounded border border-dashed border-slate-500/40 bg-deep-card/30 mb-1"
                   data-test="design-unrecognized">
                {{ item.name || item.module_id }}
              </div>
            </div>
          </div>
        </div>

        <!-- 结构检查（环 / 孤岛 / 悬空边）与替代结构判定 -->
        <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div class="p-3 rounded-xl bg-deep-card/40 border border-deep-border" data-test="design-graph-checks">
            <div class="text-[11px] text-gray-400 mb-1">结构检查</div>
            <div class="text-[11px] text-gray-300 leading-relaxed">
              {{ report.graph_checks.counts.nodes }} 个模块 · {{ report.graph_checks.counts.edges }} 条依赖 ·
              {{ report.graph_checks.counts.cycles }} 个环 · {{ report.graph_checks.counts.orphans }} 个孤岛 ·
              {{ report.graph_checks.counts.dangling_edges }} 条悬空边 · 最大层级深度 {{ report.graph_checks.max_depth }}
            </div>
            <ul v-if="report.graph_checks.cycles.length" class="mt-2 space-y-1">
              <li v-for="(cycle, i) in report.graph_checks.cycles" :key="'c' + i" class="text-[11px] text-amber-300">
                环：{{ cycle.path }}
              </li>
            </ul>
          </div>
          <div class="p-3 rounded-xl bg-deep-card/40 border border-deep-border" data-test="design-alternatives">
            <div class="text-[11px] text-gray-400 mb-1">可接受替代结构</div>
            <div class="text-[11px] text-gray-300 leading-relaxed">
              {{ report.alternatives.available
                ? (report.alternatives.accepted ? ('命中：' + (report.alternatives.accepted_alternative || '')) : '本轮没有命中任何一条教师给定的替代结构（这不等于设计错）')
                : report.alternatives.reason_cn }}
            </div>
            <ul v-if="report.alternatives.violations?.length" class="mt-2 space-y-1">
              <li v-for="(item, i) in report.alternatives.violations" :key="'v' + i" class="text-[11px] text-amber-300">
                禁止合并：{{ item.a }} + {{ item.b }}{{ item.reason_cn ? '（' + item.reason_cn + '）' : '' }}
              </li>
            </ul>
          </div>
        </div>

        <!-- 提交本身的结构性问题与未知字段（如实列出，不静默丢弃） -->
        <div v-if="report.submission_issues?.length || report.submission_warnings?.unknown_fields?.length"
             class="mt-4 p-3 rounded-xl bg-amber-500/5 border border-amber-500/25" data-test="design-submission-issues">
          <div class="text-[11px] text-amber-400 mb-1">提交本身的问题</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in report.submission_issues" :key="'si' + i" class="text-[11px] text-amber-200/90">· {{ line }}</li>
            <li v-if="report.submission_warnings?.unknown_fields?.length" class="text-[11px] text-gray-400">
              · 引擎不认识的字段（原样记录、未参与评审）：{{ report.submission_warnings.unknown_fields.join('、') }}
            </li>
          </ul>
        </div>

        <!-- 报告自己的诚实边界（引擎给的 caveats，原样展示） -->
        <div v-if="report.caveats?.length" class="mt-5 pt-4 border-t border-deep-border" data-test="design-caveats">
          <div class="text-[11px] text-gray-500 mb-2">这份报告的边界（引擎原文，不是免责声明）</div>
          <ul class="space-y-1">
            <li v-for="(line, i) in report.caveats" :key="i" class="text-[11px] text-gray-400 leading-relaxed flex gap-2">
              <span class="text-gray-600">·</span><span>{{ line }}</span>
            </li>
          </ul>
        </div>

        <div class="text-[11px] text-gray-600 mt-3 font-mono">
          图谱 source_hash {{ (report.source_hash || '').slice(0, 12) || '未给出' }}
          · 任务 {{ report.task_id }} · 提交 {{ report.submission_id || '（未命名）' }}
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
/**
 * 阶段四「设计画布」+ 阶段五「六维评审」（README §18 优先级 3 / §12.4 / §9.1–9.2）。
 *
 * 这个组件做什么
 * ==============
 * 1. 从后端取一道**分级设计任务**（题干 + 需求简报 + 「本次有几项必备能力」），
 *    **必备能力清单不下发**给学生（§10.5 字段可见性矩阵）；
 * 2. 提供一张原生画布：加模块、拖动、改名、删除、连依赖、填模块卡片、写设计理由；
 * 3. 提交后调用后端六维评审，把结果**原样**渲染：每一维的 ``status`` / ``score`` /
 *    ``findings`` / ``issues`` / ``signals`` 都来自引擎，前端不加一个字、不折算一个分数；
 * 4. 第 2 次提交起显示与上一轮的对比（README §12.4 的「最小功能集」最后一条）。
 *
 * 四条不许违反的纪律
 * ==================
 * 1. **反馈区提交前一个节点都不渲染**（``v-if="report"``，README §12.6 第 1 条）；
 * 2. **算不出来的维度不许显示成 0**：``status !== 'evaluated'`` 时页面显示「本轮未评估 + 原因」，
 *    总分显示 ``—``（引擎给的是 ``null``）；
 * 3. **判定不在这里做**：六维评审只有一份实现 —— 后端的 ``engine/design/rubric.py``。
 *    离线模式下如实说「设计任务不可用 / 评审不可用」，绝不在浏览器里算一份口径不同的分数；
 * 4. **草稿只存本机**：``lwai.design.draft.<project_id>.<task_id>``（与阶段一 / 二的草稿键同构）。
 *    **报告不持久化**：它是「针对某一份图谱的某一次提交」的结论，``source_hash`` 变了以后再显示就是拿旧结论糊弄学生。
 *
 * 画布为什么不用第三方图库
 * ========================
 * README §12.4 的首选方案：原生 drag + 手写 SVG。仓库里 ``package-lock.json`` 出现的
 * cytoscape / d3 / dagre 全是 mermaid 的**传递依赖**，不能被直接 import（升级 mermaid 就会消失）。
 * 节点坐标存在数据里、连线路径由坐标算出，所以不依赖 DOM 测量 —— jsdom 走查里也能被断言。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { listDesignTasks, loadDesignTask, evaluateDesignSubmission } from '../api/dataSource'

const props = defineProps({
  /** 项目 id：设计任务与评审都靠它定位 */
  projectId: {
    type: String,
    default: '',
  },
})

/** 节点宽度（写死是必要的：连线端点要由坐标算，不能依赖 DOM 测量） */
const NODE_W = 200
const NODE_H = 64

const loading = ref(false)
const loadError = ref('')
const taskList = ref([])
const currentTaskId = ref('')
const task = ref(null)

const nodes = ref([])
const edges = ref([])
const rationale = ref('')
const selection = ref(null) // { kind: 'node' | 'edge', id | edge }
const nextId = ref(1)

const submitting = ref(false)
const submitError = ref('')
const report = ref(null)
const history = ref([]) // [{ iteration, overall_score, evaluated_dimensions, scores: {key: score} }]

/** 拖拽与连线过程中的临时状态（不进入提交数据） */
const drag = ref(null)
const linkDraft = ref(null)

const canvasEl = ref(null)

const selectedNode = computed(() =>
  selection.value?.kind === 'node' ? nodes.value.find((n) => n.id === selection.value.id) || null : null,
)
const selectionLabel = computed(() => {
  if (selection.value?.kind === 'node') return '模块'
  if (selection.value?.kind === 'edge') return '连线'
  return ''
})
const canSubmit = computed(() => nodes.value.length > 0 && !submitting.value)

const briefModeLabel = computed(() => {
  const mode = task.value?.brief?.mode
  if (mode === 'capabilities') return '已给出功能需求清单（考归类）'
  if (mode === 'flows') return '给的是流程线索（考流程与模块的对应）'
  return '只给规模数字（模块由你自己拆）'
})

/** 与上一轮的对比（README §12.4：修改后再次提交 → 显示与上一轮的对比）。 */
const comparison = computed(() => {
  if (history.value.length < 2 || !report.value) return ''
  const prev = history.value[history.value.length - 2]
  const now = history.value[history.value.length - 1]
  const parts = []
  if (prev.overall_score !== null && now.overall_score !== null) {
    const delta = Math.round((now.overall_score - prev.overall_score) * 10) / 10
    parts.push(`总分 ${prev.overall_score} → ${now.overall_score}（${delta >= 0 ? '+' : ''}${delta}）`)
  } else {
    parts.push(`总分 ${prev.overall_score ?? '—'} → ${now.overall_score ?? '—'}`)
  }
  for (const dim of report.value.dimensions) {
    const before = prev.scores?.[dim.key]
    const after = dim.status === 'evaluated' ? dim.score : null
    if (before === null || before === undefined || after === null) continue
    if (Math.abs(before - after) < 0.05) continue
    parts.push(`「${dim.name}」${before} → ${after}`)
  }
  parts.push(`本轮评估覆盖 ${now.evaluated_dimensions}/${report.value.total_dimensions} 维`)
  return `与上一轮对比：${parts.join('；')}。`
})

// ---------------------------------------------------------------------------
// 草稿持久化（只存草稿，不存报告）
// ---------------------------------------------------------------------------
function draftKey(projectId, taskId) {
  return `lwai.design.draft.${projectId || 'default'}.${taskId || 'default'}`
}

function saveDraft() {
  try {
    localStorage.setItem(
      draftKey(props.projectId, currentTaskId.value),
      JSON.stringify({
        nodes: nodes.value,
        edges: edges.value,
        rationale: rationale.value,
        nextId: nextId.value,
      }),
    )
  } catch {
    /* 隐私模式下 localStorage 不可用时只丢持久化能力，不影响设计流程 */
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(draftKey(props.projectId, currentTaskId.value))
    if (!raw) return false
    const parsed = JSON.parse(raw)
    nodes.value = Array.isArray(parsed.nodes) ? parsed.nodes : []
    edges.value = Array.isArray(parsed.edges) ? parsed.edges : []
    rationale.value = typeof parsed.rationale === 'string' ? parsed.rationale : ''
    nextId.value = Number(parsed.nextId) || nodes.value.length + 1
    return nodes.value.length > 0 || edges.value.length > 0
  } catch {
    return false
  }
}

function markDirty() {
  saveDraft()
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------
async function load() {
  const id = props.projectId
  loading.value = true
  loadError.value = ''
  report.value = null
  submitError.value = ''
  history.value = []
  task.value = null
  taskList.value = []
  nodes.value = []
  edges.value = []
  rationale.value = ''
  selection.value = null
  nextId.value = 1

  const listing = await listDesignTasks(id)
  if (!listing.ok) {
    loading.value = false
    loadError.value = listing.offline
      ? '离线演示模式：设计任务不可用（题干、需求简报与六维评审都在后端执行）'
      : (listing.error || '任务清单加载失败')
    return
  }
  taskList.value = listing.data.tasks || []
  currentTaskId.value = listing.data.default_task_id || (taskList.value[0]?.task_id ?? '')

  const res = await loadDesignTask(id, currentTaskId.value)
  loading.value = false
  if (!res.ok) {
    loadError.value = res.offline
      ? '离线演示模式：设计任务不可用（题干与需求简报由后端下发）'
      : (res.error || '设计任务加载失败')
    return
  }
  task.value = res.data
  loadDraft()
}

/** 换一道题：结论清空，画布按该题的草稿重新加载。 */
async function switchTask() {
  report.value = null
  submitError.value = ''
  history.value = []
  nodes.value = []
  edges.value = []
  rationale.value = ''
  selection.value = null
  nextId.value = 1

  const res = await loadDesignTask(props.projectId, currentTaskId.value)
  if (!res.ok) {
    loadError.value = res.error || '设计任务加载失败'
    return
  }
  loadError.value = ''
  task.value = res.data
  loadDraft()
}

onMounted(load)
watch(() => props.projectId, load)
watch(currentTaskId, () => {
  if (task.value && task.value.task_id !== currentTaskId.value) switchTask()
})

// ---------------------------------------------------------------------------
// 画布操作
// ---------------------------------------------------------------------------
function otherNodes(node) {
  return nodes.value.filter((n) => n.id !== node.id)
}

function isNodeSelected(node) {
  return selection.value?.kind === 'node' && selection.value.id === node.id
}

function isEdgeSelected(edge) {
  return selection.value?.kind === 'edge' && selection.value.from === edge.from && selection.value.to === edge.to
}

/**
 * 添加模块。给了坐标就用坐标（双击空白处），否则按网格顺序摆放（点按钮）。
 * 自动摆放是必要的：按钮路径不该依赖鼠标位置，走查里也要能稳定复现。
 */
function addModule(position = null) {
  const index = nodes.value.length
  const x = position?.x ?? 24 + (index % 3) * (NODE_W + 18)
  const y = position?.y ?? 24 + Math.floor(index / 3) * (NODE_H + 34)
  const node = {
    id: `m${nextId.value}`,
    name: '',
    x: Math.max(0, Math.round(x)),
    y: Math.max(0, Math.round(y)),
    objective: '',
    inputs: [],
    outputs: [],
    does_not: [],
    business_rules: [],
    state_changes: [],
    exceptions: [],
    parent_id: null,
    depends_on: [],
  }
  nextId.value += 1
  nodes.value.push(node)
  selection.value = { kind: 'node', id: node.id }
  markDirty()
  return node
}

function removeNode(node) {
  nodes.value = nodes.value.filter((n) => n.id !== node.id)
  edges.value = edges.value.filter((e) => e.from !== node.id && e.to !== node.id)
  nodes.value.forEach((n) => {
    if (n.parent_id === node.id) n.parent_id = null
    n.depends_on = (n.depends_on || []).filter((d) => d !== node.id)
  })
  if (isNodeSelected(node)) selection.value = null
  markDirty()
}

function removeSelection() {
  if (selection.value?.kind === 'node') {
    const node = nodes.value.find((n) => n.id === selection.value.id)
    if (node) removeNode(node)
    return
  }
  if (selection.value?.kind === 'edge') {
    removeEdge(selection.value)
  }
}

function removeEdge(edge) {
  edges.value = edges.value.filter((e) => !(e.from === edge.from && e.to === edge.to))
  if (isEdgeSelected(edge)) selection.value = null
  markDirty()
}

function selectNode(node) {
  selection.value = { kind: 'node', id: node.id }
}

function selectEdge(edge) {
  selection.value = { kind: 'edge', from: edge.from, to: edge.to }
}

/** 双击空白处加模块（点在节点上时不加：那是改名/拖动的地盘）。 */
function onCanvasDblClick(event) {
  if (event.target.closest?.('[data-test="design-node"]')) return
  const rect = canvasEl.value?.getBoundingClientRect?.()
  const baseX = rect && rect.left ? event.clientX - rect.left : event.offsetX || 120
  const baseY = rect && rect.top ? event.clientY - rect.top : event.offsetY || 120
  addModule({ x: baseX - NODE_W / 2, y: baseY - NODE_H / 2 })
}

// ---- 拖动节点 ----
function startDrag(node, event) {
  selection.value = { kind: 'node', id: node.id }
  const rect = canvasEl.value?.getBoundingClientRect?.()
  const originX = rect && rect.left ? event.clientX - rect.left : event.offsetX || 0
  const originY = rect && rect.top ? event.clientY - rect.top : event.offsetY || 0
  drag.value = { id: node.id, dx: originX - node.x, dy: originY - node.y, moved: false }
}

function onCanvasMouseMove(event) {
  if (!drag.value) return
  const rect = canvasEl.value?.getBoundingClientRect?.()
  const x = rect && rect.left ? event.clientX - rect.left : event.offsetX || 0
  const y = rect && rect.top ? event.clientY - rect.top : event.offsetY || 0
  const node = nodes.value.find((n) => n.id === drag.value.id)
  if (!node) return
  node.x = Math.max(0, Math.round(x - drag.value.dx))
  node.y = Math.max(0, Math.round(y - drag.value.dy))
  drag.value.moved = true
}

function onCanvasMouseUp() {
  if (drag.value) {
    if (drag.value.moved) saveDraft()
    drag.value = null
  }
  linkDraft.value = null
}

// ---- 连依赖（从节点右侧圆点拖到另一个节点） ----
function startLink(node, event) {
  event.stopPropagation?.()
  linkDraft.value = { from: node.id }
}

function finishLink(node, event) {
  if (!linkDraft.value) return
  event.stopPropagation?.()
  const from = linkDraft.value.from
  linkDraft.value = null
  if (!from || from === node.id) return
  const exists = edges.value.some((e) => e.from === from && e.to === node.id)
  if (!exists) {
    edges.value.push({ from, to: node.id, type: 'uses' })
    markDirty()
  }
}

/** 贝塞尔路径（由坐标算出，不依赖 DOM 测量）。 */
function edgePath(edge) {
  const from = nodes.value.find((n) => n.id === edge.from)
  const to = nodes.value.find((n) => n.id === edge.to)
  if (!from || !to) return ''
  const x1 = from.x + NODE_W
  const y1 = from.y + NODE_H / 2
  const x2 = to.x
  const y2 = to.y + NODE_H / 2
  const dx = Math.max(30, Math.abs(x2 - x1) * 0.5)
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
}

const linkDraftPath = computed(() => {
  if (!linkDraft.value) return ''
  const from = nodes.value.find((n) => n.id === linkDraft.value.from)
  if (!from) return ''
  const x1 = from.x + NODE_W
  const y1 = from.y + NODE_H / 2
  const x2 = x1 + 60
  return `M ${x1} ${y1} C ${x1 + 30} ${y1}, ${x2 - 30} ${y1}, ${x2} ${y1}`
})

// ---------------------------------------------------------------------------
// 文本字段：多行文本 ↔ 数组
// ---------------------------------------------------------------------------
function linesToText(value) {
  return Array.isArray(value) ? value.join('\n') : (value || '')
}

function setLines(node, field, event) {
  node[field] = String(event.target.value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  markDirty()
}

// ---------------------------------------------------------------------------
// 提交：生成 design_submission.json（README §10.4 契约）
// ---------------------------------------------------------------------------
/** 层级由父链算出（根 = 1），不让学生手填 —— 手填的 level 与 parent_id 迟早会打架。 */
function levelOf(node, guard = 0) {
  if (!node.parent_id || guard > 8) return 1
  const parent = nodes.value.find((n) => n.id === node.parent_id)
  if (!parent) return 1
  return levelOf(parent, guard + 1) + 1
}

function buildSubmission() {
  // iteration 由**历史记录**算出，不由 report 算出：submit() 会先清空 report（不把旧结论留在屏幕上），
  // 用 report 算就会每次都退回 1（走查抓到的真实 bug：第二次提交仍显示「第 1 次提交」）。
  const iteration = history.value.length + 1
  return {
    submission_id: `sub_${props.projectId || 'project'}_${iteration}`,
    task_id: currentTaskId.value,
    iteration,
    modules: nodes.value.map((node) => ({
      module_id: node.id,
      name: node.name,
      level: levelOf(node),
      parent_id: node.parent_id || null,
      objective: node.objective || '',
      inputs: node.inputs || [],
      outputs: node.outputs || [],
      does_not: node.does_not || [],
      business_rules: node.business_rules || [],
      state_changes: node.state_changes || [],
      exceptions: node.exceptions || [],
      depends_on: node.depends_on || [],
    })),
    relations: edges.value.map((edge) => ({ from: edge.from, to: edge.to, type: edge.type || 'uses' })),
    flow_designs: [],
    design_rationale: rationale.value,
  }
}

function pushHistory(data) {
  const scores = {}
  for (const dim of data.dimensions || []) {
    scores[dim.key] = dim.status === 'evaluated' ? dim.score : null
  }
  history.value.push({
    iteration: data.iteration,
    overall_score: data.overall_score,
    evaluated_dimensions: data.evaluated_dimensions,
    scores,
  })
}

function normalizedWeight(key) {
  const found = (report.value?.weights || []).find((item) => item.key === key)
  return found ? found.normalized_weight : null
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''

  // ⚠️ 顺序很重要：**先按当前画布构造提交，再清空上一份报告**。
  // 反过来写会出真 bug：iteration 会被算回 1，第二次提交看起来还像第一次
  // （`scripts/browser_clickthrough.mjs` 的「iteration 递增」断言抓到的就是这个）。
  const submission = buildSubmission()
  report.value = null
  const res = await evaluateDesignSubmission(props.projectId, currentTaskId.value, submission)
  submitting.value = false

  if (!res.ok) {
    submitError.value = res.error || '评审失败'
    return
  }
  report.value = res.data
  pushHistory(res.data)
}
</script>

<style scoped>
.stage-design input::placeholder,
.stage-design textarea::placeholder {
  color: #4b5563;
}
</style>
