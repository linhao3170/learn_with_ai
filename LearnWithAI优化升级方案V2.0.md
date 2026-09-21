# LearnWithAI 优化升级方案 V2.0 - 完整实施版

## 🚧 实施进展快照（实时更新）

> 每次继续开发前先看这一节，快速了解当前状态和下一步。

### 当前阶段

**Phase 1 进行中：项目级分析引擎 + 引导式训练前端原型**

已从"函数级分析"推进到"项目级业务逻辑理解训练"，核心是**四关引导式训练 + 完整业务逻辑结果页**，而不是单纯做题。

### 已完成

| 模块 | 状态 | 说明 |
|------|------|------|
| Python AST 解析层 | ✅ | 类/函数/docstring/import 提取，行号证据完整 |
| 函数级模式识别 | ✅ | 7 种业务模式（CRUD、验证、异常处理等），借鉴 bandit 规则引擎 |
| 调用图 & 知识点 | ✅ | 函数级调用关系、6 大类 20+ 知识点 |
| **项目级分析引擎** | ✅ | `engine/project_analyzer/`：模块识别、职责推断、依赖分析、核心度评分、流程提取、四关题生成 |
| 演示项目 | ✅ | `sample_projects/lab_safety_assistant/`（预约/设备/安全检查/用户 4 模块） |
| 前端框架 | ✅ | Vue 3 + Vite + Tailwind CSS，深色科技风 |
| 引导式训练首页 | ✅ | `TrainingView.vue`，默认为训练页 |
| **四关训练闭环** | ✅ | 功能拆分 → 模块职责 → 流程推演 → 关键实现，答题、评分、进度全跑通 |
| **完整业务逻辑结果页** | ✅ | 得分概览 + 模块架构 + 核心业务流程 + 模块职责清单 + 能力评估 |
| 完整分析详情页 | ✅ | 概览 / 业务模式 / 流程图 / 代码结构 / 知识点 / 闯关测试，六个 tab |
| 前端烟雾测试 | ✅ | `frontend/scripts/smoke_training.cjs`，验证训练状态链路 |

### 已知不足（当前分析为什么"还不够深"）

现在的分析是**纯规则 + 关键词匹配**，不调用任何模型 API，零成本可离线跑，但深度有限：

- 核心流程还是"单模块内方法列表"，不是真正的跨模块调用链
- 模块依赖图是基础版 import 级别，没有调用级别的依赖强度
- 没有状态流转识别（不知道哪些方法改了哪些状态字段）
- 关键实现只有"选思路"的题，没有"为什么这么设计"的深度解析
- 训练题干扰项是硬编码列表，不是根据项目上下文动态生成

这些是下一步重点，也是"完整业务逻辑呈现"真正有料的前提。

### 下一步优先级（按顺序做）

1. **深化规则引擎——跨模块调用链 & 核心流程提取**
   - 做真正的方法级调用图（跨文件、跨模块）
   - 从入口方法出发，提取完整业务流程链路
   - 识别状态变更点（哪些方法写了哪些实例属性）
   - 目标：结果页的"核心业务流程"是真正的跨模块数据流，不是单模块方法列表

2. **模块依赖图可视化**
   - 依赖方向、依赖强度、核心模块高亮
   - 前端结果页可点击模块看详情

3. **关键实现深度解析**
   - 不只是选择题，还要讲清楚设计思路、边界条件、异常处理
   - 第 4 关从"选答案"升级为"分析 + 引导"

4. **答错引导路径**
   - 每关答错后，不是直接给答案，而是引导回到对应模块/流程重新思考
   - 这才是"培养业务逻辑"和"做题"的核心区别

5. **后端服务化（FastAPI）**
   - 支持上传项目 → 实时分析 → 生成训练
   - 现在是前端读预生成 JSON，后端接上才是真正可用的产品

6. **LLM 语义增强（最后再做）**
   - 不着急上。等规则引擎能提取的"事实"足够丰富了再接
   - 架构：规则引擎负责确定性事实（类、方法、调用、依赖），LLM 只负责自然语言归纳和引导语生成
   - 接入方式：Dify 工作流编排，国产模型为主（DeepSeek-V3 主力，GLM-4-Flash 兜底）
   - 成本估算：一次中型项目分析约 ¥0.1-0.3
   - 可信度保证：结构化输出 + schema 校验 + 证据追溯 + 人工可编辑

### 怎么跑起来

```bash
# 前端
cd frontend
npm install
npm run dev          # http://localhost:5173/

# 训练逻辑烟雾测试（验证四关 + 结果页状态链路）
node scripts/smoke_training.cjs
```

### 关键文件索引

| 文件 | 作用 |
|------|------|
| `README.md` | 项目对外说明 + 路线图 |
| `engine/project_analyzer/main.py` | 项目级分析引擎入口 |
| `engine/project_analyzer/module_analyzer.py` | 模块识别、职责、依赖、核心流程 |
| `engine/project_analyzer/training_generator.py` | 四关训练题生成 |
| `sample_projects/lab_safety_assistant/` | 演示项目（4 模块） |
| `frontend/src/views/TrainingView.vue` | 引导式训练主页（四关 + 结果页） |
| `frontend/src/App.vue` | 应用主框架（训练页 / 分析详情页切换） |
| `frontend/public/demo/project_analysis.json` | 预生成的演示数据 |
| `frontend/scripts/smoke_training.cjs` | 训练逻辑烟雾测试 |

---

## 📋 项目核心目标与需求

### 项目核心目标

**培养业务逻辑理解能力，而非单纯编码能力**  

在 AI 辅助编程时代，学生可以轻松用 AI 生成代码，但往往不理解代码的业务逻辑。本平台通过”理解验证”机制，确保学生真正掌握代码背后的业务含义。

### 核心功能需求

#### 1. 两种学习模式
- **模式1（业务学习）**：直接学习老师的标准答案 → 可视化展示 → 闯关测试
- **模式2（作业提交）**：提交代码 → 功能验证 → 闯关测试 → 未通过则引导学习

#### 2. 五大技术模块
1. **代码业务逻辑分析引擎**：自动识别业务模式、核心函数、知识点
2. **交互式流程图**：SVG 可视化 + 可点击节点查看代码
3. **三道闯关题生成**：代码识别 → 逻辑理解 → 综合应用
4. **知识图谱系统**：跟踪学生掌握情况，识别薄弱点
5. **私有化部署**：Docker 一键部署，无外部依赖

#### 3. 关键约束
- ✅ 支持多语言（Python、Java、JavaScript 等）
- ✅ 私有化部署优先
- ✅ LLM 增强但不依赖（核心基于 AST 静态分析）
- ✅ 教育效果可量化

---

## 🎯 核心价值主张

### 教育定位
LearnWithAI 是一个**业务逻辑理解能力培养平台**，而非传统的代码编写训练平台。在 AI 辅助编程时代，学生可以轻松获得可运行的代码，但往往不理解其业务逻辑。本平台通过”理解验证”机制，确保学生真正掌握代码的业务含义。

### 技术定位
- **私有化部署优先**：支持教育机构内网部署
- **多语言代码分析**：支持 Python、Java、JavaScript 等主流语言
- **LLM 增强但不依赖**：核心功能基于 AST 静态分析，LLM 仅用于辅助生成题目
- **渐进式学习路径**：从业务理解到代码实现的完整闭环

---

## 二、技术架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────┐
│                  前端层 (Vue 3)                      │
│  - 教师管理端  - 学生学习端  - 可视化展示           │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│                API 网关层 (Traefik)                  │
│  - 路由管理  - 负载均衡  - HTTPS 自动化              │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              后端服务层 (FastAPI)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ 用户服务  │  │ 题目服务  │  │ 代码分析服务     │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ 学习服务  │  │ 评估服务  │  │ 知识图谱服务     │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│                 数据层                                │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ PostgreSQL   │  │  Redis   │  │  MinIO       │  │
│  │ (主数据库)    │  │ (缓存)    │  │ (文件存储)   │  │
│  └──────────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────┘
```

**技术选型理由**：
- **Vue 3**：轻量级、生态成熟、适合教育类交互界面
- **FastAPI**：高性能、原生异步支持、自动 API 文档生成
- **PostgreSQL**：开源、支持 JSONB、适合复杂查询
- **Redis**：高速缓存，减少重复的代码分析开销
- **MinIO**：兼容 S3 协议的私有对象存储

### 2.2 重构后的系统架构

#### 三大核心功能模块

```
┌─────────────────────────────────────────────────────┐
│           LearnWithAI 核心平台                       │
└─────────────────────────────────────────────────────┘
                       ↓
        ┌──────────────┴──────────────┐
        ↓                              ↓
┌──────────────────┐         ┌──────────────────┐
│  核心引擎（独立） │         │   应用层（三端）  │
└──────────────────┘         └──────────────────┘
        ↓                              ↓
┌──────────────────┐         ┌──────────────────┐
│ 业务逻辑分析引擎  │         │ 1. 教师上传端    │
│ - AST静态解析    │         │ 2. 学生答题端    │
│ - LLM语义理解    │         │ 3. 学习探索端    │
│ - SVG流程图生成  │         └──────────────────┘
│ - 知识点提取     │
└──────────────────┘
```

### 2.3 核心引擎：业务逻辑分析系统

**设计原则：** 独立、可复用、高内聚

```python
# 核心架构
business_logic_analyzer/
├── __init__.py
├── parser/                    # 代码解析层
│   ├── ast_parser.py         # AST静态分析
│   ├── code_structure.py     # 代码结构提取
│   └── dependency_graph.py   # 依赖关系图
├── analyzer/                  # 业务分析层
│   ├── logic_decomposer.py   # 5维度业务拆解
│   ├── flow_analyzer.py      # 执行流程分析
│   └── knowledge_extractor.py # 知识点提取
├── visualizer/                # 可视化层
│   ├── svg_generator.py      # SVG流程图生成
│   ├── interactive_diagram.py # 交互式图表
│   └── learning_map.py       # 学习路径图
└── llm/                       # LLM接口层
    ├── prompt_templates.py   # Prompt模板库
    └── model_adapter.py      # 模型适配器
```

---

## 三、核心模块实施方案

### 3.1 代码业务逻辑分析引擎

#### 3.1.1 技术选型

**主要方案：Tree-sitter + 自定义分析层**

**GitHub 资源**：
- [tree-sitter-language-pack](https://github.com/Goldziher/tree-sitter-language-pack) - 支持 371 种语言的统一解析器
- [code_ast](https://github.com/cedricrupb/code_ast) - 基于 tree-sitter 的快速 AST 解析库
- [ai-codeindex](https://pypi.org/project/ai-codeindex/0.20.0/) - 提取符号、继承关系、调用图

**选型理由**：
1. **多语言支持**：Tree-sitter 是增量解析器，支持 Python、Java、JavaScript 等主流语言
2. **性能优越**：纯 Rust 实现，解析速度快
3. **准确性高**：基于语法树而非正则表达式，可靠性强
4. **开源成熟**：GitHub 官方项目，活跃维护

#### 3.1.2 分析流程

```python
# 伪代码示例
class BusinessLogicAnalyzer:
    def __init__(self):
        self.parser = TreeSitterParser()  # 使用 tree-sitter
        self.pattern_detector = PatternDetector()
        
    def analyze(self, code: str, language: str):
        # 步骤1：解析 AST
        ast = self.parser.parse(code, language)
        
        # 步骤2：提取结构信息
        functions = self.extract_functions(ast)
        classes = self.extract_classes(ast)
        imports = self.extract_imports(ast)
        
        # 步骤3：分析业务模式
        patterns = self.pattern_detector.detect([
            'CRUD',           # 增删改查
            'file_operation', # 文件操作
            'data_validation',# 数据验证
            'error_handling', # 异常处理
            'api_call',       # API 调用
        ])
        
        # 步骤4：构建调用图
        call_graph = self.build_call_graph(functions)
        
        # 步骤5：生成流程描述
        flow = self.generate_flow(call_graph, patterns)
        
        return {
            'overview': self.generate_overview(patterns),
            'modules': self.group_by_module(functions, classes),
            'functions': functions,
            'patterns': patterns,
            'flow': flow,
            'knowledge_points': self.extract_knowledge_points(patterns)
        }
```

**实施难点与解决方案**：

| 难点 | 解决方案 |
|-----|---------|
| **多语言解析差异** | 使用 [tree-sitter-language-pack](https://docs.tree-sitter-language-pack.xberg.io/) 统一接口 |
| **业务模式识别准确性** | 建立模式库，结合启发式规则（如函数名包含 "create/add" → CRUD-C） |
| **复杂代码的分析深度** | 采用分层分析：先识别入口函数，再递归分析调用链 |
| **性能问题（大文件）** | 使用 Redis 缓存分析结果，按文件哈希值存储 |

### 3.2 交互式流程图生成

#### 3.2.1 技术选型

**方案：Mermaid.js（文本定义）+ D3.js（交互增强）**

**GitHub 资源**：
- [mermaid](https://github.com/mermaid-js/mermaid) - 文本转流程图的标准方案
- [mermaid-land](https://github.com/haroldjcastillo/mermaid-land) - Mermaid + D3.js 交互示例
- [SCAST](https://github.com/davidkingzyb/SCAST) - 代码转 UML 和流程图的完整方案

**实施方案**：

```javascript
// 前端流程图渲染组件
class InteractiveFlowChart {
  constructor(flowData) {
    this.flowData = flowData;
    this.mermaid = require('mermaid');
    this.d3 = require('d3');
  }
  
  async render(containerId) {
    // 步骤1：从后端接收流程数据，生成 Mermaid 语法
    const mermaidSyntax = this.generateMermaidSyntax(this.flowData);
    
    // 步骤2：渲染为 SVG
    const { svg } = await this.mermaid.render('flowchart', mermaidSyntax);
    
    // 步骤3：使用 D3.js 增强交互
    const svgElement = d3.select(`#${containerId}`).html(svg);
    
    // 添加点击事件：点击节点 → 显示对应代码片段
    svgElement.selectAll('.node').on('click', (event, d) => {
      const nodeId = d3.select(event.currentTarget).attr('id');
      this.showCodeSnippet(nodeId);
    });
    
    // 添加悬停效果
    svgElement.selectAll('.node')
      .on('mouseover', function() {
        d3.select(this).style('opacity', 0.7);
      })
      .on('mouseout', function() {
        d3.select(this).style('opacity', 1);
      });
  }
  
  generateMermaidSyntax(flowData) {
    // 示例：学生管理系统的流程
    return `
      flowchart TD
        A[开始] --> B[加载学生数据]
        B --> C{显示菜单}
        C -->|选择1| D[添加学生]
        C -->|选择2| E[删除学生]
        C -->|选择3| F[查询学生]
        C -->|选择4| G[退出]
        D --> H[保存数据]
        E --> H
        H --> C
        F --> C
        G --> I[结束]
        
        click B "showCode#load_students" "查看加载代码"
        click D "showCode#add_student" "查看添加代码"
    `;
  }
}
```

**选型理由**：
1. **Mermaid**：文本定义，易于后端生成；支持多种图表类型
2. **D3.js**：强大的 SVG 操作能力，可添加复杂交互
3. **可缓存**：生成的 SVG 可直接存储到数据库，减少重复计算

### 3.3 闯关题目生成系统

#### 3.3.1 三道闯关题设计

**参考论文**：[Chatbot-Based Assessment of Code Understanding](https://arxiv.org/html/2604.07304)

| 关卡 | 题型 | 目的 | 示例 |
|-----|------|------|------|
| **关卡1** | 代码填空选择题 | 测试代码识别能力 | "下列哪段代码实现了'添加学生'功能？" |
| **关卡2** | 业务逻辑选择题 | 测试流程理解 | "当用户输入无效ID时，系统会执行什么操作？" |
| **关卡3** | 逻辑引导式复现 | 测试综合应用 | "请按照提示完成'删除学生'功能的关键步骤" |

#### 3.3.2 题目生成策略

**基础方案（无 LLM）**：
```python
class QuizGenerator:
    def generate_level1_quiz(self, functions: List[Function]):
        """关卡1：从真实函数中提取，生成代码识别题"""
        target_func = random.choice(functions)
        
        # 创建干扰项：修改函数名或关键逻辑
        distractors = self.create_code_distractors(target_func)
        
        return {
            'question': f'以下哪段代码实现了"{target_func.purpose}"功能？',
            'options': [target_func.code] + distractors,
            'answer': 'A'
        }
    
    def generate_level2_quiz(self, flow_graph: FlowGraph):
        """关卡2：基于流程图生成逻辑题"""
        decision_node = self.find_decision_nodes(flow_graph)[0]
        
        return {
            'question': f'在"{decision_node.context}"情况下，系统会执行什么操作？',
            'options': [
                decision_node.true_branch.description,   # 正确答案
                decision_node.false_branch.description,  # 干扰项1
                self.generate_plausible_distractor(),    # 干扰项2
                "抛出异常并退出程序"                       # 干扰项3
            ],
            'answer': 'A'
        }
```

**增强方案（可选 LLM）**：
- 使用本地部署的小模型（如 [Ollama](https://ollama.ai/) + Llama 3.2）
- 仅用于生成更自然的题目描述和干扰项
- **关键**：题目答案基于代码静态分析，不依赖 LLM 生成

### 3.4 知识图谱系统

#### 3.4.1 技术方案

**简化方案：PostgreSQL JSONB**

```sql
-- 学生知识图谱表
CREATE TABLE student_knowledge_graph (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(20) UNIQUE NOT NULL,
    
    -- 已掌握的业务模式（JSONB 格式）
    mastered_patterns JSONB DEFAULT '[]',
    -- 示例：['CRUD', 'file_operation', 'recursion']
    
    -- 每个模式的掌握程度（JSONB 格式）
    pattern_proficiency JSONB DEFAULT '{}',
    -- 示例：{'CRUD': 0.85, 'file_operation': 0.90}
    
    -- 薄弱知识点
    weak_points JSONB DEFAULT '[]',
    -- 示例：['exception_handling', 'boundary_check']
    
    -- 学习轨迹（JSONB 数组）
    learning_history JSONB DEFAULT '[]',
    -- 示例：[{'date': '2024-01-01', 'problem_id': 'P001', 'score': 85}]
    
    -- 统计数据
    total_problems_learned INTEGER DEFAULT 0,
    average_score FLOAT DEFAULT 0,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- JSONB 索引加速查询
CREATE INDEX idx_mastered_patterns ON student_knowledge_graph USING GIN (mastered_patterns);
CREATE INDEX idx_weak_points ON student_knowledge_graph USING GIN (weak_points);
```

**选型理由**：
- PostgreSQL 的 JSONB 性能优异（支持索引）
- 避免引入图数据库（如 Neo4j），降低部署复杂度
- 足以支持中小规模教育机构（1000+ 学生）

---

## 四、前端 UI 设计方案

### 4.1 技术栈

**核心框架**：Vue 3 + TypeScript + Vite  
**UI 组件库**：Element Plus（中文友好、文档完善）  
**可视化库**：
- Mermaid.js（流程图）
- ECharts（统计图表）
- D3.js（高级交互）

**参考项目**：
- [full-stack-fastapi-vue](https://github.com/orlan0045/full-stack-fastapi-vue-simplified) - 完整的 FastAPI + Vue 3 脚手架
- [code-executives](https://github.com/mnaimfaizy/code-executives) - 80+ 编程可视化教育平台

### 4.2 关键页面设计

#### 4.2.1 学生学习页面（模式1）

```vue
<template>
  <div class="learning-container">
    <!-- 顶部导航 -->
    <el-page-header @back="goBack" :content="problemTitle" />
    
    <!-- 主体区域：左右分栏 -->
    <el-row :gutter="20">
      <!-- 左侧：业务逻辑展示 -->
      <el-col :span="14">
        <el-card class="analysis-card">
          <h3>📊 功能概述</h3>
          <p>{{ analysisData.overview }}</p>
          
          <el-divider />
          
          <h3>🔧 核心模块</h3>
          <el-collapse v-model="activeModules">
            <el-collapse-item 
              v-for="module in analysisData.modules" 
              :key="module.name"
              :title="module.name"
              :name="module.name">
              <CodeHighlight :code="module.code" :language="language" />
            </el-collapse-item>
          </el-collapse>
          
          <el-divider />
          
          <h3>💡 知识点标注</h3>
          <el-tag 
            v-for="kp in analysisData.knowledge_points" 
            :key="kp.name"
            @click="showKnowledgeDetail(kp)"
            class="knowledge-tag">
            {{ kp.name }}
          </el-tag>
        </el-card>
        
        <el-button 
          type="primary" 
          size="large" 
          @click="startChallenge"
          class="start-btn">
          ✓ 我已理解，开始测试
        </el-button>
      </el-col>
      
      <!-- 右侧：交互式流程图 -->
      <el-col :span="10">
        <el-card class="flowchart-card">
          <h3>📈 执行流程</h3>
          <div id="flowchart-container" ref="flowchartRef"></div>
          <el-alert 
            type="info" 
            :closable="false"
            show-icon>
            💡 点击节点可查看对应代码
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { InteractiveFlowChart } from '@/utils/flowchart';
import CodeHighlight from '@/components/CodeHighlight.vue';

// 从后端获取分析数据
const analysisData = ref({});
const flowchartRef = ref(null);

onMounted(async () => {
  // 调用 API 获取业务逻辑分析
  const response = await fetch(`/api/student/problem/${problemId}/business-logic`);
  analysisData.value = await response.json();
  
  // 渲染交互式流程图
  const flowChart = new InteractiveFlowChart(analysisData.value.flow);
  await flowChart.render('flowchart-container');
});
</script>
```

#### 4.2.2 闯关测试页面

```vue
<template>
  <div class="challenge-container">
    <el-progress 
      :percentage="progress" 
      :format="formatProgress" />
    
    <el-card class="question-card">
      <h2>关卡{{ currentLevel }}：{{ questionType }}</h2>
      <div class="question-content" v-html="currentQuestion.content"></div>
      
      <!-- 选择题 -->
      <el-radio-group 
        v-if="currentQuestion.type === 'choice'"
        v-model="userAnswer">
        <el-radio 
          v-for="(option, index) in currentQuestion.options" 
          :key="index"
          :label="index"
          class="option-radio">
          <CodeHighlight 
            v-if="option.isCode" 
            :code="option.text" 
            :language="language" />
          <span v-else>{{ option.text }}</span>
        </el-radio>
      </el-radio-group>
      
      <!-- 代码填空题（关卡3） -->
      <div v-if="currentQuestion.type === 'guided_code'">
        <el-steps :active="codeStep" align-center>
          <el-step 
            v-for="(step, idx) in currentQuestion.steps" 
            :key="idx"
            :title="step.title" />
        </el-steps>
        
        <CodeEditor 
          v-model="userCode" 
          :template="currentQuestion.template"
          :hints="currentQuestion.hints" />
      </div>
    </el-card>
    
    <el-button 
      type="primary" 
      @click="submitAnswer"
      :disabled="!userAnswer">
      {{ isLastQuestion ? '提交答案' : '下一题' }}
    </el-button>
  </div>
</template>
```

---

## 五、私有化部署方案

### 5.1 Docker Compose 完整配置

**参考项目**：[Docker-PostgreSQL-Redis-Boilerplate](https://github.com/adityarizqi/Docker-PostgreSQL-Redis-Boilerplate)

```yaml
version: '3.8'

services:
  # 前端服务
  frontend:
    build: ./frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./frontend/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend
    networks:
      - learnwithai-network

  # 后端 API 服务
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/learnwithai
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
    volumes:
      - ./backend:/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - learnwithai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # PostgreSQL 数据库
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: learnwithai
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - learnwithai-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis 缓存
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    networks:
      - learnwithai-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # MinIO 对象存储
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio-data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - learnwithai-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

volumes:
  postgres-data:
  redis-data:
  minio-data:

networks:
  learnwithai-network:
    driver: bridge
```

### 5.2 一键部署脚本

```bash
#!/bin/bash
# deploy.sh

echo "🚀 开始部署 LearnWithAI 平台..."

# 检查 Docker 环境
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 未检测到 Docker Compose，请先安装"
    exit 1
fi

# 创建必要的目录
mkdir -p ./data/{postgres,redis,minio}
mkdir -p ./logs

# 设置环境变量
cp .env.example .env
echo "📝 请编辑 .env 文件配置数据库密码等信息"
read -p "按 Enter 继续..."

# 构建镜像
echo "🔨 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo "▶️  启动服务..."
docker-compose up -d

# 等待服务就绪
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🔍 检查服务状态..."
docker-compose ps

# 初始化数据库
echo "📊 初始化数据库..."
docker-compose exec backend python scripts/init_db.py

echo "✅ 部署完成！"
echo "📌 访问地址："
echo "   - 前端: http://localhost"
echo "   - API 文档: http://localhost:8000/docs"
echo "   - MinIO 控制台: http://localhost:9001"
```

### 5.3 系统要求

**最低配置**（适合小规模试用，< 100 用户）：
- CPU: 4 核
- 内存: 8 GB
- 存储: 50 GB SSD
- 操作系统: Ubuntu 22.04 LTS / CentOS 8+

**推荐配置**（适合中等规模，500-1000 用户）：
- CPU: 8 核
- 内存: 16 GB
- 存储: 200 GB SSD
- 操作系统: Ubuntu 22.04 LTS

---

## 六、核心难点与解决方案

### 6.1 难点1：多语言代码分析的准确性

**问题**：不同编程语言的语法差异大，业务模式识别困难。

**解决方案**：
1. **统一抽象层**：使用 [tree-sitter-language-pack](https://docs.tree-sitter-language-pack.xberg.io/) 提供统一的 AST 访问接口
2. **模式库设计**：建立语言无关的业务模式定义
   ```python
   PATTERNS = {
       'CRUD_CREATE': {
           'keywords': ['add', 'create', 'insert', 'new'],
           'ast_patterns': ['function_call → insert', 'method_call → save']
       },
       'FILE_READ': {
           'keywords': ['read', 'load', 'open'],
           'ast_patterns': ['open() → read()', 'File.read()']
       }
   }
   ```
3. **渐进式支持**：先支持 Python、Java、JavaScript，后续逐步扩展

### 6.2 难点2：闯关题目的质量保证

**问题**：自动生成的题目可能存在逻辑错误或难度不均。

**解决方案**：
1. **人工审核机制**：教师可以预览和修改自动生成的题目
2. **题目质量评估**：
   ```python
   class QuizQualityEvaluator:
       def evaluate(self, quiz, student_responses):
           # 计算区分度：高分学生答对率 vs 低分学生答对率
           discrimination = self.calculate_discrimination(quiz, student_responses)
           
           # 计算难度：答对率
           difficulty = sum(r.is_correct for r in student_responses) / len(student_responses)
           
           # 自动标记低质量题目
           if discrimination < 0.2 or difficulty < 0.3 or difficulty > 0.9:
               quiz.mark_as_low_quality()
   ```
3. **题库迭代优化**：收集学生反馈，持续改进

### 6.3 难点3：大规模并发时的性能

**问题**：多学生同时提交代码分析请求，系统压力大。

**解决方案**：
1. **分层缓存**：
   - L1：Redis 缓存（按代码哈希值，TTL 1小时）
   - L2：PostgreSQL 缓存表（长期存储）
2. **异步任务队列**：
   ```python
   from fastapi import BackgroundTasks
   
   @app.post("/api/student/submission/submit")
   async def submit_code(code: str, background_tasks: BackgroundTasks):
       # 立即返回提交ID
       submission_id = generate_id()
       
       # 后台异步分析
       background_tasks.add_task(analyze_code_async, submission_id, code)
       
       return {"submission_id": submission_id, "status": "processing"}
   ```
3. **资源限制**：单个代码分析任务限制在 30 秒内，超时返回简化分析

### 6.4 难点4：私有化部署后的维护

**问题**：教育机构 IT 能力参差不齐，运维困难。

**解决方案**：
1. **健康检查面板**：
   ```python
   @app.get("/health")
   async def health_check():
       return {
           "database": check_postgres_connection(),
           "redis": check_redis_connection(),
           "disk_space": get_disk_usage(),
           "memory": get_memory_usage()
       }
   ```
2. **自动化备份**：
   ```bash
   # 每日自动备份数据库
   0 2 * * * docker-compose exec postgres pg_dump -U user learnwithai > /backup/$(date +\%Y\%m\%d).sql
   ```
3. **详细文档**：提供故障排查手册和常见问题解答

---

## 七、项目实施时间表

### 7.1 阶段1：核心功能开发（8 周）

| 周次 | 任务 | 交付物 |
|-----|------|--------|
| Week 1-2 | 环境搭建 + 基础架构 | Docker Compose 配置、数据库设计 |
| Week 3-4 | 代码分析引擎开发 | 支持 Python 的 AST 解析和模式识别 |
| Week 5-6 | 流程图生成 + 前端页面 | 交互式流程图、学习页面 |
| Week 7-8 | 闯关题目生成系统 | 3 种题型的自动生成 |

### 7.2 阶段2：功能完善（4 周）

| 周次 | 任务 | 交付物 |
|-----|------|--------|
| Week 9-10 | 知识图谱系统 | 学生学习轨迹跟踪 |
| Week 11-12 | 多语言支持扩展 | 支持 Java、JavaScript |

### 7.3 阶段3：测试与优化（4 周）

| 周次 | 任务 | 交付物 |
|-----|------|--------|
| Week 13-14 | 系统测试 + 性能优化 | 测试报告、优化方案 |
| Week 15-16 | 试点部署 + 用户反馈 | 试用报告、改进计划 |

**总计：16 周（约 4 个月）**

---

## 八、开源项目清单

### 8.1 核心依赖

| 项目 | 用途 | GitHub 地址 | Stars |
|-----|------|------------|-------|
| **tree-sitter-language-pack** | 多语言代码解析 | [链接](https://github.com/Goldziher/tree-sitter-language-pack) | 活跃项目 |
| **code_ast** | AST 快速解析 | [链接](https://github.com/cedricrupb/code_ast) | 200+ |
| **SCAST** | 代码转 UML/流程图 | [链接](https://github.com/davidkingzyb/SCAST) | 参考实现 |
| **mermaid** | 流程图生成 | [链接](https://github.com/mermaid-js/mermaid) | 70k+ |
| **FastAPI** | 后端框架 | [链接](https://github.com/tiangolo/fastapi) | 75k+ |
| **full-stack-fastapi-vue** | 项目脚手架 | [链接](https://github.com/orlan0045/full-stack-fastapi-vue-simplified) | 500+ |

### 8.2 参考项目

| 项目 | 参考价值 | GitHub 地址 |
|-----|---------|------------|
| **Simplyfi** | 代码可视化 + 聊天功能 | [链接](https://github.com/BinaryBardAkshat/Simplyfi) |
| **code-executives** | 80+ 编程教育可视化 | [链接](https://github.com/mnaimfaizy/code-executives) |
| **educates-training-platform** | Kubernetes 教育平台 | [链接](https://github.com/educates/educates-training-platform) |

---

## 九、技术风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|------|---------|
| Tree-sitter 解析精度不足 | 中 | 高 | 建立测试用例库，覆盖常见代码模式 |
| 多语言支持复杂度超预期 | 高 | 中 | 采用渐进式策略，优先支持 Python |
| 闯关题目质量不稳定 | 中 | 中 | 人工审核 + 质量评估算法 |
| 性能瓶颈 | 低 | 中 | 缓存策略 + 异步处理 |
| 私有部署兼容性问题 | 中 | 低 | 提供多系统测试环境 |

---

## 十、成功标准

### 10.1 技术指标
- ✅ 代码分析准确率 > 85%（基于人工标注的测试集）
- ✅ 单次分析响应时间 < 5 秒（500 行以内代码）
- ✅ 系统并发支持 100+ 用户
- ✅ 部署成功率 > 95%（在标准 Ubuntu 22.04 环境）

### 10.2 教育效果指标
- ✅ 学生业务逻辑理解度提升 > 30%（前后测对比）
- ✅ 闯关通过率 60%-80%（过低说明题目太难，过高说明太简单）
- ✅ 教师满意度 > 4.0/5.0

---

## 十一、MVP 范围与验收标准

### 11.1 MVP 必须完成的范围

MVP 只承诺一条可测量的闭环：

**教师上传 Python 题目和参考测试 → 系统生成带源码行号证据的业务逻辑图 → 教师审核并发布三道闯关题 → 学生学习或提交作业 → 在隔离沙箱中运行测试 → 给出功能分、理解分、薄弱点和补救路径。**

MVP 的语言范围先限定为 **Python 3.11/3.12**；前端和后端的接口设计保留多语言字段，但不在第一期承诺 Java、C/C++、Go 的同等分析质量。

### 11.2 明确不在 MVP 承诺的事情

- ❌ 不承诺"检测出所有 AI 生成代码"或"证明学生独立完成"
- ❌ 不把大模型输出直接作为最终成绩；关键事实必须有静态分析证据
- ❌ 不在浏览器直接运行学生代码；浏览器只编辑和提交
- ❌ 不允许上传任意仓库后默认递归克隆互联网
- ❌ 不一开始拆成十几个微服务，也不先上 Kubernetes
- ❌ 不把 Mermaid 生成的 SVG 字符串当作交互数据

### 11.3 验收口径

以下目标是验收指标，不是未经测试的宣传数字：

| 指标 | 定义 | MVP 目标 |
|---|---|---:|
| **解析成功率** | 评测集内能生成合法 AST 和源码行号 | 支持 Python 样本 ≥98% |
| **关键事实准确率** | 模块、核心函数、主流程等由教师标注的事实 | precision/recall 各 ≥85% |
| **证据覆盖率** | 每个对外展示的事实能回指文件、起止行和 AST 类型 | ≥95% |
| **题目可用率** | 经过自动验证后教师无需改答案即可发布的题目比例 | ≥90% |
| **教师接受率** | 试用教师对题目和分析的 4/5 以上评分比例 | ≥80% |
| **分析耗时** | 1,000 行以内 Python 项目，从排队到结果（p95） | ≤60 秒 |
| **运行隔离** | 沙箱逃逸、宿主文件读取、未授权网络访问测试 | 0 次成功 |
| **可恢复性** | 备份后恢复数据库和对象文件 | 演练环境成功恢复 |

---

## 十二、数据模型与 API 设计

### 12.1 核心数据表设计

```sql
-- 1. 题目修订版本表
CREATE TABLE problem_revisions (
  id UUID PRIMARY KEY,
  problem_id UUID NOT NULL REFERENCES problems(id),
  revision_no INTEGER NOT NULL,
  source_hash CHAR(64) NOT NULL,
  language VARCHAR(32) NOT NULL,
  rubric JSONB NOT NULL,
  test_bundle_id UUID,
  status VARCHAR(16) NOT NULL CHECK (status IN ('draft','review','published','archived')),
  created_by UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (problem_id, revision_no),
  UNIQUE (problem_id, source_hash)
);

-- 2. 业务逻辑分析结果表
CREATE TABLE analysis_runs (
  id UUID PRIMARY KEY,
  revision_id UUID NOT NULL REFERENCES problem_revisions(id),
  schema_version VARCHAR(32) NOT NULL,
  parser_versions JSONB NOT NULL,
  prompt_version VARCHAR(64),
  model_id VARCHAR(128),
  model_digest VARCHAR(128),
  status VARCHAR(24) NOT NULL,
  artifact JSONB,
  diagnostics JSONB,
  duration_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. 学生提交表
CREATE TABLE submissions (
  id UUID PRIMARY KEY,
  revision_id UUID NOT NULL REFERENCES problem_revisions(id),
  student_id UUID NOT NULL REFERENCES users(id),
  source_artifact_id UUID NOT NULL,
  functional_score NUMERIC(5,2),
  understanding_score NUMERIC(5,2),
  final_score NUMERIC(5,2),
  status VARCHAR(24) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX submissions_student_revision
  ON submissions (student_id, revision_id, created_at DESC);
CREATE INDEX analysis_runs_revision_status
  ON analysis_runs (revision_id, status, created_at DESC);
```

### 12.2 分析产物的统一契约

分析结果保存为带证据的结构化文档，而非不可检索的长文本：

```json
{
  "schema_version": "logic.v1",
  "project_revision": "sha256:...",
  "language": "python",
  "overview": {
    "text": "从输入到输出的业务目标",
    "evidence": [{"file": "app/main.py", "start": 8, "end": 24}],
    "confidence": 0.91
  },
  "nodes": [
    {
      "id": "logic.load_data",
      "kind": "module",
      "label": "加载学生数据",
      "responsibility": "从 JSON 文件读取并校验记录",
      "symbols": ["load_students"],
      "evidence": [{"file": "app/store.py", "start": 10, "end": 31}],
      "knowledge_points": ["文件读写", "数据校验"],
      "confidence": 0.96
    }
  ],
  "edges": [
    {
      "source": "logic.load_data",
      "target": "logic.menu",
      "kind": "calls",
      "evidence": [{"file": "app/main.py", "start": 18, "end": 18}]
    }
  ],
  "knowledge_points": [
    {
      "id": "exception_handling",
      "label": "异常处理",
      "locations": ["logic.save"]
    }
  ]
}
```

**关键规则**：
- 没有 evidence 的事实不能出现在学生默认视图
- 所有文件路径必须是规范化后的相对路径
- unsupported 状态的结论只能进入教师待审核区

### 12.3 主要 API 接口

```text
# 教师端
POST   /api/v1/teacher/problems
POST   /api/v1/teacher/problems/{id}/revisions
POST   /api/v1/teacher/revisions/{id}/analysis-jobs
GET    /api/v1/teacher/analysis-runs/{id}
PATCH  /api/v1/teacher/analysis-runs/{id}/artifact
POST   /api/v1/teacher/revisions/{id}/challenge-sets
POST   /api/v1/teacher/challenge-sets/{id}/publish

# 学生端
GET    /api/v1/student/problems/{id}
POST   /api/v1/student/problems/{id}/learning-sessions
GET    /api/v1/student/learning-sessions/{id}/workspace
POST   /api/v1/student/learning-sessions/{id}/start-challenge
POST   /api/v1/student/submissions
GET    /api/v1/student/submissions/{id}
POST   /api/v1/student/submissions/{id}/enter-remediation

# 健康检查
GET    /api/v1/health/live
GET    /api/v1/health/ready
```

### 12.4 异步任务状态管理

所有耗时任务返回 `job_id`，前端通过 SSE 订阅状态：

```text
queued → validating → parsing → graphing → semantic_extracting
       → validating_artifact → ready
       ├→ needs_review
       ├→ failed_retryable
       └→ failed_permanent
```

SSE 事件格式：
```text
event: job.status
data: {"job_id":"job_123","status":"running","stage":"sandbox_tests","progress":0.65}

event: job.status
data: {"job_id":"job_123","status":"ready","resource_id":"sub_456"}
```

---

## 十三、安全与隔离设计

### 13.1 威胁模型

学生提交的代码可以尝试：
- 读取环境变量和数据库连接
- 访问内网服务
- 消耗无限 CPU/内存
- 创建子进程
- 逃逸容器
- 利用依赖漏洞

### 13.2 代码执行沙箱的最小安全基线

每次执行使用一次性工作目录和只读基础镜像：

**必须满足的条件**：
- ✅ 非 root 用户运行
- ✅ rootless container（不挂载 Docker socket）
- ✅ seccomp、AppArmor/SELinux
- ✅ cgroup 限制：CPU/内存/PID/磁盘上限
- ✅ 默认无网络、无宿主目录、无云凭据
- ✅ 设置 wall-clock、CPU、输出大小限制
- ✅ 测试结束后销毁容器和临时卷
- ✅ 高风险部署使用 gVisor 或 Firecracker

**执行接口示例**：
```json
{
  "execution_id": "exec_01",
  "language": "python",
  "image_digest": "sha256:...",
  "source_artifact": "obj://submissions/...",
  "test_bundle": "obj://tests/problem_revision_7",
  "limits": {
    "wall_ms": 5000,
    "cpu_ms": 3000,
    "memory_mb": 256,
    "pids": 32,
    "output_kb": 256,
    "network": "deny"
  }
}
```

### 13.3 输入安全检查

**上传时必须完成的检查**：
1. 限制压缩包大小、解压后大小、文件数量
2. 拒绝符号链接、设备文件和路径穿越
3. 只读取 allowlist 扩展名
4. 计算每个文件的 SHA-256
5. GitHub 导入默认只允许公共仓库和配置的域名
6. 禁止重定向到内网地址（防止 SSRF）

---

## 十四、真正的难点与处理策略

| 难点 | 为什么是真的难 | 第一阶段策略 | 后续策略 |
|---|---|---|---|
| **业务含义不是 AST 字段** | "订单已支付""学生可删除"需要领域上下文 | 题目说明 + 测试名 + 带证据 LLM 草稿 + 人审 | 领域模板和学校知识库 |
| **Python 动态行为** | 反射、装饰器、运行时注册让静态调用图不完整 | exact/candidate/runtime_observed 分级 | 运行时 tracing 和框架适配器 |
| **题目正确但没教学价值** | 模型能生成漂亮选择题，却考不到关键理解 | 模板、知识点覆盖、教师审核 | 难度标定和项目级题库 |
| **功能分和理解分混淆** | 代码跑通不代表能解释 | 测试证据与理解题分开，权重可配置 | 用课堂数据校准量规 |
| **执行不可信代码** | 隔离配置错误可能泄露主机和内网 | rootless + 无网络 + 一次性环境 | gVisor/Firecracker |
| **课堂等待时间** | 本地模型冷启动可能超过学生耐心 | 教师预分析、缓存、异步进度 | vLLM 批处理、预生成题库 |
| **大项目上下文** | 整仓库输入会超上下文并增加幻觉 | 入口切片、符号图、分层检索 | 增量分析和跨服务索引 |
| **模型升级漂移** | 同一提示词不保证同一答案 | model_digest/prompt_version、人审 | 版本门禁和灰度发布 |

---

## 十五、总结

### 15.1 项目核心亮点

本方案基于以下**真实可用的开源资源**：
1. **代码分析**：Tree-sitter 系列项目（成熟、活跃）
2. **可视化**：Mermaid.js + D3.js（行业标准）
3. **架构**：FastAPI + Vue 3 + PostgreSQL（经过验证的技术栈）
4. **部署**：Docker Compose（简单可靠）

**核心优势**：
- ✅ 技术方案可落地，无技术空想
- ✅ 私有化部署友好，无外部依赖
- ✅ 开发周期可控（4 个月 MVP）
- ✅ 渐进式实施，风险可控

### 11.2 创新点

#### 1. 独立的业务逻辑分析引擎
- **创新**：将分析能力抽象为独立模块，可复用于多种场景
- **技术**：AST 静态分析 + LLM 语义理解混合方案
- **优势**：比纯 LLM 准确，比纯规则灵活

#### 2. 双模式学习路径
- **创新**：模式1（学习优先）+ 模式2（检测优先），满足不同学习场景
- **优势**：学生可以先学习理解，也可以先提交验证

#### 3. 交互式 SVG 流程图
- **创新**：不是静态图片，而是可点击、可展开的学习工具
- **技术**：Mermaid + 自定义 SVG 增强
- **优势**：学生可以边看图边学代码

#### 4. 知识图谱跟踪
- **创新**：持续跟踪学生掌握的业务模式，识别薄弱环节
- **技术**：PostgreSQL JSONB 存储
- **优势**：无需引入复杂的图数据库

### 15.3 与 V2.0 初版的关键改进

| V2.0 初版做法 | 实际问题 | V2.0 完整版的做法 | 改进原因 |
|---|---|---|---|
| 以"逻辑相似度 85%"表示理解 | 结构相似不代表能解释边界条件 | 用测试、逻辑节点覆盖、三层题目组合评分 | 把不可验证的数字改成可追溯证据 |
| 学生代码可直接在应用容器运行 | 恶意代码可能读取密钥、数据库 | 独立 runner + gVisor/严格 rootless 容器 | 学生提交是不可信输入 |
| Mermaid SVG 作为核心存储 | SVG 可能有 XSS；难以更新节点 | 存 graph JSON，前端 React Flow 渲染 | 数据和展示解耦 |
| 上传时只保存代码，首次访问才分析 | 学生第一次打开会等待 LLM 任务 | 教师审核流程预生成 | 把高耗时操作移出课堂 |
| 直接承诺多语言和大项目 | 没有统一证据模型和评测集 | Python MVP；其余语言插件化 | 缩小首期风险 |
| Compose 使用 latest、开发热重载 | 无法复现，重启可能拉到不兼容版本 | 固定镜像 digest、生产无 reload | 私有环境需要可审计 |
| 默认接入外部 Claude/API | 与"数据不出校园"冲突 | 本地模型为默认；外部模型可选 | 满足离线和隐私要求 |

### 15.4 下一步行动

#### Phase 0：准备阶段（第 1 周）
1. **需求冻结**：确认 Python MVP、两种模式、评分权重
2. **建立评测集**：收集 10-15 个教师题目样本
3. **金标准标注**：建立 30 个函数/项目的标注模板
4. **技术选型验证**：验证 Tree-sitter 解析效果
5. **仓库初始化**：建立项目结构、CI/CD

#### Phase 1：核心引擎（第 2-4 周）
1. **安全输入**：实现上传、解包、SHA-256 计算
2. **AST 解析**：Python 语法树提取、行号映射
3. **调用图**：生成节点/边、缓存机制
4. **测试验证**：解析成功率 ≥98%

#### Phase 2：分析与可视化（第 5-8 周）
1. **LLM 集成**：接入 Ollama，实现结构化抽取
2. **流程图生成**：React Flow 交互式图表
3. **题目生成**：三层题型自动生成和验证
4. **代码沙箱**：隔离执行环境

#### Phase 3：应用层（第 9-12 周）
1. **后端 API**：FastAPI 接口、权限、任务队列
2. **教师端**：题目创建向导、分析审核
3. **学生端**：学习模式和作业提交模式
4. **双模式打通**：补救学习路径

#### Phase 4：测试与部署（第 13-16 周）
1. **集成测试**：金标准评测、性能测试
2. **安全测试**：SSRF、XSS、沙箱逃逸
3. **小班试用**：10-20 名学生试点
4. **文档交付**：部署手册、用户手册

---

## 十六、测试与评测策略

### 16.1 测试分层

**单元测试**：
- 路径清理、hash 计算、AST facts 提取
- Schema 校验、评分逻辑、权限策略

**属性测试**：
- 任意合法 Python 文件不会生成越界行号
- 同一 revision 的排序和 hash 稳定

**集成测试**：
- 上传 → 分析 → 审核 → 发布 → 学习/提交 → runner → 报告

**模型回归测试**：
- 固定输入和模型摘要，检查 JSON schema
- 证据覆盖和关键字段验证
- 模型升级必须人工复核差异

**浏览器测试**：
- Playwright 覆盖教师发布、学生学习
- 提交失败、补救和断线重连

**安全测试**：
- 恶意压缩包、SSRF、XSS、越权
- 提示注入、资源耗尽、runner 逃逸

**容量测试**：
- 队列积压、数据库连接、SSE 连接
- 对象存储和模型显存

### 16.2 金标准数据集构建

为每个样本记录：
1. **业务目标**：输入输出、功能概述
2. **模块划分**：2-5 个模块及其职责
3. **主流程**：关键步骤和分支
4. **核心函数**：函数名、参数、返回值、证据行号
5. **知识点**：边界条件、异常处理
6. **测试和题目答案**：标准答案和可接受的等价解释

**标注要求**：
- 至少由一名教师和一名开发者独立标注
- 讨论分歧，对"业务模块命名"这类主观项报告一致性
- 不把单一人工答案当绝对真值

### 16.3 评测报告必须包含

1. **分组结果**：按语言、项目大小、框架和功能类型
2. **失败案例**：分析成功但事实错误的样例
3. **降级行为**：LLM 不可用、语法错误、测试超时时的处理
4. **资源消耗**：CPU、RAM、GPU、tokens、队列等待
5. **教师修改率**：教师对自动生成结果的修改比例
6. **学生完成率**：学习模式和作业模式的完成情况
7. **学习效果**：前后测和定性反馈（样本不足时不声称统计显著）

### 16.4 持续质量保证

**代码质量**：
- 使用 Semgrep/ast-grep 做静态规则检查
- 复杂度、命名、重复检测（不作为理解分）

**题目质量评估**：
```python
class QuizQualityEvaluator:
    def evaluate(self, quiz, student_responses):
        # 区分度：高分学生答对率 vs 低分学生答对率
        discrimination = self.calculate_discrimination(quiz, student_responses)
        
        # 难度：答对率
        difficulty = sum(r.is_correct for r in student_responses) / len(student_responses)
        
        # 自动标记低质量题目
        if discrimination < 0.2 or difficulty < 0.3 or difficulty > 0.9:
            quiz.mark_as_low_quality()
            return {'quality': 'low', 'reason': '区分度或难度不合适'}
        
        return {'quality': 'acceptable'}
```

---

## 十七、部署与运维

### 17.1 推荐的三种部署形态

| 形态 | 适用场景 | 组件 | 权衡 |
|---|---|---|---|
| **单机 CPU** | 课堂演示、无 GPU 小班 | API、worker、PostgreSQL、队列、llama.cpp | 成本低；语义分析等待更长 |
| **单机 GPU** | 10-30 人试点 | 上述组件 + Ollama 或 vLLM | 最易落地；并发需要排队 |
| **分离服务** | 多班级或多 GPU | API/DB、分析 worker、runner、推理节点分开 | 扩展好；运维复杂 |

### 17.2 资源估算起点

| 配置 | CPU/RAM | GPU | 建议任务排队能力 | 说明 |
|---|---|---|---:|---|
| **演示** | 4 vCPU / 16 GB | 无或小型消费 GPU | 1-3 | 主要展示预生成结果 |
| **小班试点** | 8-16 vCPU / 32-64 GB | 24 GB 级起步 | 5-15 | runner 与推理必须设配额 |
| **多班级** | 16+ vCPU / 64+ GB | 48 GB 级或多卡 | 压测决定 | 分离各服务节点 |

**注意**：这些数字不是性能承诺。课堂体验的关键是教师提前分析、学生读取缓存和明确的进度 UI。

### 17.3 离线和内网部署要点

**离线部署清单**：
1. 在联网构建机下载并固定镜像、Python wheels、npm 包
2. 下载 grammar、模型和 runner 镜像，生成 SBOM 和 hash 清单
3. 通过学校内部镜像仓库或受控介质导入
4. 离线主机不执行 `docker pull latest`、`npm install` 或模型自动下载

**内网部署配置**：
- 完全离线时默认关闭 GitHub 导入
- 证书使用学校 CA
- 模型、数据库和对象存储只绑定内网地址
- 更新采用新目录、迁移演练、切换、保留上一版本
- 每晚备份 PostgreSQL，每日备份对象文件

### 17.4 生产环境检查清单

#### 功能检查
- [ ] 一个题目 revision 可以从上传完整走到发布
- [ ] 学习模式不依赖学生提交代码，刷新后进度可恢复
- [ ] 作业模式可运行隐藏测试并形成可解释结果
- [ ] 未通过理解检测可以进入补救学习并重新答题
- [ ] 教师可校正分析和题目，学生看不到隐藏答案

#### 质量检查
- [ ] 金标准评测结果达到目标，失败样本已归档
- [ ] 每个学生可见结论都能定位源码或测试证据
- [ ] 题目 schema、唯一答案、L3 执行检查全部通过
- [ ] 模型、解析器、prompt 和 migration 版本已冻结

#### 安全和合规检查
- [ ] runner 无网络、无宿主挂载、无 Docker socket
- [ ] 上传、GitHub、Markdown、SVG 和提示注入测试通过
- [ ] RBAC 和班级隔离通过，审计日志可查询
- [ ] 源码、学生数据、模型和第三方依赖许可证已登记
- [ ] 备份恢复和离线安装演练完成

#### 运维检查
- [ ] 所有镜像和模型有 sha256 清单，生产没有 latest
- [ ] API、worker、runner、数据库、队列有健康检查
- [ ] 任务失败可重试或进入人工队列
- [ ] 发布包能在无外网新主机按文档启动
- [ ] 保留上一版本和数据库回滚方案

### 17.5 监控与告警

**关键指标**：
- API 响应时间（p50、p95、p99）
- 任务队列长度和等待时间
- 数据库连接池使用率
- Redis 内存使用率
- 模型推理 tokens/s
- Runner 执行成功率
- 缓存命中率

**告警规则**：
- API p95 响应时间 > 3 秒
- 队列积压 > 50 个任务且持续 5 分钟
- 数据库连接池 > 80%
- 磁盘使用率 > 85%
- Runner 失败率 > 10%

---

## 十八、最终交付物清单

1. **可运行系统**
   - Docker Compose 发布包（CPU 和 GPU 配置）
   - 所有镜像的 SHA-256 清单
   - 模型权重和量化版本

2. **后端服务**
   - FastAPI/OpenAPI 接口文档
   - PostgreSQL 数据库 migration 脚本
   - 权限矩阵和审计日志说明

3. **核心引擎**
   - Python 业务逻辑分析引擎
   - Graph JSON Schema 规范
   - 解析器和模型版本记录

4. **前端应用**
   - 教师题目审核界面
   - 学生学习模式界面
   - 学生作业提交界面
   - 补救学习和报告界面

5. **执行环境**
   - 隔离执行 runner
   - 测试镜像和安全配置
   - 安全测试报告

6. **测试与评测**
   - 金标准数据集（去除敏感信息）
   - 评测脚本和结果报告
   - 单元测试和集成测试

7. **文档**
   - 教师使用手册
   - 学生使用手册
   - 部署/备份/恢复手册
   - 故障排查手册

8. **演示材料**
   - 5-8 分钟演示流程
   - 答辩 PPT
   - 已知限制清单

9. **合规材料**
   - 开源依赖清单（SBOM）
   - 许可证声明
   - 第三方组件版本锁定

---

## 十九、参考资源汇总

**代码分析相关**：
- [Tree-sitter 官方文档](https://tree-sitter.github.io/)
- [Tree-sitter Language Pack](https://docs.tree-sitter-language-pack.xberg.io/)
- [How I Parse 14 Languages With One Function](https://medium.com/@aakash.m.g/how-i-parse-14-languages-with-one-function-codewalk-deep-dives-1-abfde4de6fb9)

**可视化相关**：
- [Mermaid 流程图语法](https://mermaid.js.org/)
- [D3.js 官方文档](https://d3js.org/)
- [Code to Flowchart Converter](https://codetoflowchart.com/)

**教育评估相关**：
- [Chatbot-Based Assessment of Code Understanding](https://arxiv.org/html/2604.07304)
- [A Framework for Concept-Based Quiz Generation](https://arxiv.org/html/2503.14662v1)

**部署相关**：
- [FastAPI Full Stack Template](https://github.com/orlan0045/full-stack-fastapi-vue-simplified)
- [Docker Compose Multi-Container Setup](https://itsourcecode.com/docker/docker-compose-multi-container-setup-2026-web-db-cache/)
- [Educates Training Platform](https://github.com/educates/educates-training-platform)

### 12.2 开源项目汇总

**代码分析工具**：
- [tree-sitter-language-pack](https://github.com/Goldziher/tree-sitter-language-pack) - 371 种语言支持
- [code_ast](https://github.com/cedricrupb/code_ast) - 快速 AST 解析
- [ai-codeindex](https://pypi.org/project/ai-codeindex/0.20.0/) - 代码索引提取
- [ast-graph](https://github.com/emtyty/ast-graph) - 代码库智能分析

**代码可视化**：
- [SCAST](https://github.com/davidkingzyb/SCAST) - 代码转 UML/流程图
- [Simplyfi](https://github.com/BinaryBardAkshat/Simplyfi) - 多语言代码可视化
- [CodeAtlas](https://github.com/lucyb0207/CodeAtlas) - GitHub 仓库依赖图
- [algorithm-visualizer](https://github.com/algorithm-visualizer/algorithm-visualizer) - 算法可视化平台

**教育平台参考**：
- [code-executives](https://github.com/mnaimfaizy/code-executives) - 80+ 编程可视化
- [educates-training-platform](https://github.com/educates/educates-training-platform) - Kubernetes 教育平台

**全栈模板**：
- [full-stack-fastapi-vue-simplified](https://github.com/orlan0045/full-stack-fastapi-vue-simplified)
- [FastAPI-Vue-OAuth2](https://github.com/jason810496/FastAPI-Vue-OAuth2)
- [fullstack-template-fastapi-react-vue](https://github.com/giladfuchs/fullstack-template-fastapi-react-vue)

---

## 📝 版本信息与变更记录

### 版本信息
- **文档版本**：V2.0 完整实施版
- **更新日期**：2026年1月
- **作者**：LearnWithAI 项目组
- **许可证**：MIT License

### 主要变更（相比原始方案）

#### ✅ 新增内容
1. **项目核心目标与需求明确化**（第一部分）
2. **详细的技术架构设计**（总体架构 + 技术选型理由）
3. **核心模块实施方案**（包含代码示例和 GitHub 资源）
4. **前端 UI 设计方案**（Vue 3 组件示例）
5. **私有化部署完整方案**（Docker Compose + 部署脚本）
6. **核心难点与解决方案**（4 大难点详细分析）
7. **项目实施时间表**（16 周详细规划）
8. **开源项目清单**（所有资源均来自真实 GitHub 项目）
9. **技术风险评估表**
10. **成功标准定义**（技术指标 + 教育效果指标）

#### 🔧 优化内容
1. 将原有的三端应用场景设计保留并整合
2. 增强了业务逻辑分析引擎的技术细节
3. 补充了完整的数据库设计
4. 添加了真实可用的参考资源链接

---

## 🎨 三大应用场景详细设计

### 场景1：教师上传题目端

**核心流程：**

```
教师上传题目文件
     ↓
自动保存到教师ID知识库
     ↓
返回题目ID（供学生访问）
```

**API设计：**

```python
POST /api/teacher/upload-problem
Request:
{
  "teacher_id": "T001",
  "title": "学生管理系统",
  "description": "实现学生信息的增删改查",
  "code_file": "base64_encoded_file",  // 或文件URL
  "language": "python",
  "tags": ["数据结构", "文件操作"]
}

Response:
{
  "problem_id": "P12345",
  "status": "success",
  "message": "题目已保存到知识库",
  "access_url": "/student/problem/P12345"
}
```

**数据库设计：**

```sql
-- 教师知识库表
CREATE TABLE teacher_problems (
    id VARCHAR(20) PRIMARY KEY,          -- P12345
    teacher_id VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    code_content TEXT NOT NULL,
    language VARCHAR(20) DEFAULT 'python',
    tags TEXT[],                         -- PostgreSQL数组类型
    
    -- 业务逻辑分析结果（延迟生成）
    logic_analysis JSONB,                -- 首次学生访问时生成
    analysis_status VARCHAR(20) DEFAULT 'pending',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_teacher_id ON teacher_problems(teacher_id);
```

---

### 场景2：学生答题端（核心复杂流程）

**完整业务流程：**

```
学生打开教师ID下的题库
     ↓
【步骤1】检测是否已分析
     ├─ 未分析 → 调用业务逻辑分析引擎
     │          ├─ AST解析
     │          ├─ 5维度业务拆解
     │          ├─ 生成SVG流程图
     │          └─ 保存分析结果到knowledge_base
     └─ 已分析 → 直接读取缓存
     ↓
【步骤2】展示题目 + 业务逻辑分析
     ↓
学生编写/上传答案代码
     ↓
【步骤3】答案初步验证
     ├─ 语法检查
     ├─ 基础功能测试
     └─ 与标准答案的业务逻辑对比
     ↓
【步骤4】生成3道闯关题
     ├─ 基于标准答案的业务逻辑
     ├─ 关卡1：代码填空选择题
     ├─ 关卡2：业务逻辑选择题
     └─ 关卡3：逻辑引导式复现题
     ↓
【步骤5】学生作答闯关题
     ↓
【步骤6】评分与反馈
     ├─ 答案正确性分析
     ├─ 理解度评分（0-100）
     └─ 薄弱知识点识别
```

**核心API设计：**

```python
# API 1: 获取题目（触发业务分析）
GET /api/student/problem/{problem_id}
Response:
{
  "problem": {
    "id": "P12345",
    "title": "学生管理系统",
    "description": "...",
    "requirements": ["功能1", "功能2"]
  },
  "business_logic": {
    "status": "analyzing" | "completed",
    "analysis": {
      "overview": "一句话概述",
      "modules": [...],
      "functions": [...],
      "flow": [...],
      "key_points": [...]
    },
    "flow_chart_svg": "<svg>...</svg>",
    "knowledge_points": ["文件操作", "数据结构"]
  }
}

# API 2: 提交答案（触发验证 + 生成闯关题）
POST /api/student/submit-answer
Request:
{
  "problem_id": "P12345",
  "student_id": "S001",
  "code": "student's code"
}

Response:
{
  "submission_id": "SUB789",
  "verification": {
    "syntax_check": "pass",
    "basic_test": "pass",
    "logic_comparison": {
      "similarity": 85,
      "missing_parts": ["异常处理不完善"],
      "status": "pass"
    }
  },
  "challenge_questions_status": "generating"  // 异步生成
}

# API 3: 获取闯关题
GET /api/student/challenges/{submission_id}
Response:
{
  "challenges": [
    {
      "level": 1,
      "type": "code_fill_blank",
      "content": {...}
    },
    {
      "level": 2,
      "type": "logic_choice",
      "content": {...}
    },
    {
      "level": 3,
      "type": "guided_implementation",
      "content": {...}
    }
  ]
}

# API 4: 提交闯关答案
POST /api/student/submit-challenges
Request:
{
  "submission_id": "SUB789",
  "answers": [
    {"level": 1, "answer": "A"},
    {"level": 2, "answer": "C"},
    {"level": 3, "code": "..."}
  ]
}

Response:
{
  "score": 85,
  "details": {
    "level1": {"correct": true, "score": 30},
    "level2": {"correct": true, "score": 30},
    "level3": {"correct": false, "score": 25, "feedback": "..."}
  },
  "weak_points": ["边界条件处理"],
  "suggestions": ["建议加强异常处理的学习"]
}
```

---

### 场景3：核心业务逻辑学习端（主页面功能）

**功能定位：** 独立的学习工具，无需题目背景

**使用场景：**
- 学生上传GitHub项目链接，快速理解项目结构
- 上传代码文件，学习核心业务逻辑
- 生成可交互的学习路径图

**核心流程：**

```
用户上传项目/代码文件
     ↓
【智能识别】
├─ 单文件代码 → 直接分析
├─ 多文件项目 → 识别入口文件
├─ GitHub链接 → 克隆 + 分析
└─ 文档文件 → 提取业务描述
     ↓
【深度分析】
├─ AST解析代码结构
├─ 识别核心业务模块
├─ 提取关键函数和数据流
└─ 生成依赖关系图
     ↓
【可视化输出】
├─ SVG交互式流程图
├─ 知识点标注体系
├─ 学习路径推荐
└─ 代码核心部分高亮
```

**API设计：**

```python
POST /api/learning/analyze-project
Request:
{
  "user_id": "U001",
  "source_type": "file" | "github" | "text",
  "content": "code or url or description",
  "options": {
    "include_visualization": true,
    "generate_learning_path": true,
    "extract_knowledge_points": true
  }
}

Response:
{
  "analysis_id": "AN001",
  "project_info": {
    "name": "学生管理系统",
    "language": "python",
    "complexity": "medium",
    "estimated_learning_time": "2-3小时"
  },
  "business_logic": {
    "overview": "实现学生信息的CRUD操作...",
    "architecture": {
      "pattern": "MVC",
      "layers": ["数据层", "业务层", "表示层"]
    },
    "core_modules": [
      {
        "name": "学生信息管理",
        "functions": ["add_student", "delete_student"],
        "key_concepts": ["文件操作", "数据验证"]
      }
    ],
    "execution_flow": [
      "1. 读取学生数据文件",
      "2. 加载到内存数据结构",
      "3. 提供增删改查接口",
      "4. 保存修改回文件"
    ],
    "key_algorithms": [
      {
        "name": "学生查找",
        "algorithm": "线性查找",
        "time_complexity": "O(n)"
      }
    ]
  },
  "visualizations": {
    "flow_chart_svg": "<svg>...</svg>",
    "dependency_graph_svg": "<svg>...</svg>",
    "architecture_diagram_svg": "<svg>...</svg>"
  },
  "knowledge_points": [
    {
      "category": "数据结构",
      "points": ["列表", "字典"],
      "locations": ["student_manager.py:15-30"]
    },
    {
      "category": "文件操作",
      "points": ["文件读写", "JSON序列化"],
      "locations": ["file_handler.py:8-25"]
    }
  ],
  "learning_path": {
    "beginner": [
      "1. 理解整体功能和数据流",
      "2. 学习Student类的定义",
      "3. 掌握文件读写操作",
      "4. 理解增删改查逻辑"
    ],
    "suggested_order": [
      "main.py → student.py → file_handler.py → student_manager.py"
    ]
  },
  "interactive_elements": {
    "clickable_nodes": true,
    "expandable_sections": true,
    "code_preview_links": [...]
  }
}
```

**前端交互设计：**

```
┌─────────────────────────────────────────────┐
│  核心业务逻辑学习平台                         │
├─────────────────────────────────────────────┤
│  [上传代码] [粘贴GitHub链接] [输入描述]      │
├─────────────────────────────────────────────┤
│                                              │
│  ┌──────────────┐    ┌──────────────────┐  │
│  │  项目概览     │    │  SVG流程图        │  │
│  │              │    │  (可缩放/可点击)   │  │
│  │  语言: Python │    │                   │  │
│  │  复杂度: 中等 │    │  ┌───┐           │  │
│  │  学习时长: 2h │    │  │开始│           │  │
│  │              │    │  └─┬─┘           │  │
│  └──────────────┘    │    ↓             │  │
│                      │  [读取数据]       │  │
│  ┌──────────────┐    │    ↓             │  │
│  │  知识点标注   │    │  [加载内存]      │  │
│  │              │    │    ↓             │  │
│  │  📍 文件操作  │←───┤  [CRUD接口]     │  │
│  │  📍 数据结构  │    │    ↓             │  │
│  │  📍 异常处理  │    │  [保存文件]      │  │
│  │              │    │    ↓             │  │
│  └──────────────┘    │  ┌───┐          │  │
│                      │  │结束│          │  │
│  ┌──────────────┐    │  └───┘          │  │
│  │  学习路径     │    │                  │  │
│  │              │    │  点击节点查看代码 │  │
│  │  Step 1 ✓    │    └──────────────────┘  │
│  │  Step 2 →    │                          │
│  │  Step 3      │    ┌──────────────────┐  │
│  │  Step 4      │    │  代码预览窗口     │  │
│  │              │    │  (Monaco Editor)  │  │
│  └──────────────┘    └──────────────────┘  │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 🔧 核心技术实现

### 1. 业务逻辑分析引擎（核心）

**5维度拆解实现：**

```python
# backend/app/core/logic_analyzer/decomposer.py

from typing import Dict, List
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

class BusinessLogicDecomposer:
    """业务逻辑5维度拆解器"""
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.parser = Parser()
        PY_LANGUAGE = Language(tspython.language())
        self.parser.set_language(PY_LANGUAGE)
    
    def decompose(self, code: str, context: str = "") -> Dict:
        """
        5维度拆解代码业务逻辑
        
        Args:
            code: 源代码
            context: 题目描述等上下文信息
        
        Returns:
            {
                "overview": "功能整体概述",
                "modules": [...],      # 核心模块划分
                "functions": [...],    # 核心函数清单
                "flow": [...],         # 主业务执行流程
                "key_points": [...]    # 关键逻辑点
            }
        """
        # Step 1: AST静态分析
        ast_info = self._parse_ast(code)
        
        # Step 2: 结构化提取
        structure = self._extract_structure(ast_info)
        
        # Step 3: LLM语义理解
        logic_analysis = self._llm_analyze(code, structure, context)
        
        # Step 4: 结果融合与验证
        result = self._merge_and_validate(structure, logic_analysis)
        
        return result
    
    def _parse_ast(self, code: str) -> Dict:
        """AST解析"""
        tree = self.parser.parse(bytes(code, "utf8"))
        root = tree.root_node
        
        return {
            "classes": self._extract_classes(root),
            "functions": self._extract_functions(root),
            "imports": self._extract_imports(root),
            "control_flow": self._extract_control_flow(root)
        }
    
    def _extract_functions(self, node) -> List[Dict]:
        """提取函数信息"""
        functions = []
        
        def traverse(n):
            if n.type == 'function_definition':
                func_name = n.child_by_field_name('name').text.decode('utf8')
                params = self._extract_parameters(n)
                returns = self._extract_return_type(n)
                body_complexity = self._calculate_complexity(n)
                
                functions.append({
                    "name": func_name,
                    "parameters": params,
                    "returns": returns,
                    "complexity": body_complexity,
                    "line_start": n.start_point[0] + 1,
                    "line_end": n.end_point[0] + 1
                })
            
            for child in n.children:
                traverse(child)
        
        traverse(node)
        return functions
    
    def _llm_analyze(self, code: str, structure: Dict, context: str) -> Dict:
        """LLM深度分析"""
        prompt = f"""
你是一位经验丰富的编程教师，请分析以下代码的核心业务逻辑。

## 代码内容
```python
{code}
```

## 代码结构信息
- 类: {len(structure['classes'])}个
- 函数: {len(structure['functions'])}个
- 主要函数: {', '.join([f['name'] for f in structure['functions'][:5]])}

## 题目背景
{context}

## 分析任务
请按照以下5个维度进行分析，以JSON格式输出：

{{
  "overview": "一句话概述这段代码的核心功能和适用场景（30字以内）",
  
  "modules": [
    {{
      "name": "模块名称",
      "responsibility": "模块职责描述",
      "key_functions": ["func1", "func2"]
    }}
  ],
  
  "functions": [
    {{
      "name": "函数名",
      "purpose": "函数作用",
      "input": "入参说明",
      "output": "返回值说明",
      "is_core": true
    }}
  ],
  
  "flow": [
    "步骤1：描述",
    "步骤2：描述",
    "步骤3：描述"
  ],
  
  "key_points": [
    {{
      "category": "算法/边界/异常",
      "description": "关键点描述",
      "location": "function_name:line_number"
    }}
  ]
}}

**要求：**
1. overview必须简洁准确，突出核心功能
2. modules按职责划分，一般2-4个模块
3. functions只列出核心函数（is_core=true的不超过5个）
4. flow按执行顺序，清晰展示数据流转
5. key_points标注影响功能正确性的关键逻辑
"""
        
        response = self.llm.generate(prompt, temperature=0.3)
        return self._parse_json_response(response)
```

### 2. SVG流程图生成器

**基于Mermaid + 增强SVG：**

```python
# backend/app/core/visualizer/svg_generator.py

import base64
from typing import Dict, List
import requests

class InteractiveSVGGenerator:
    """交互式SVG流程图生成器"""
    
    def generate_flow_chart(self, flow_data: List[str], 
                           knowledge_points: Dict) -> str:
        """
        生成可交互的SVG流程图
        
        Args:
            flow_data: 业务流程步骤列表
            knowledge_points: 知识点标注信息
        
        Returns:
            SVG字符串（包含交互逻辑）
        """
        # Step 1: 生成Mermaid代码
        mermaid_code = self._generate_mermaid(flow_data)
        
        # Step 2: 转换为SVG
        svg_base = self._mermaid_to_svg(mermaid_code)
        
        # Step 3: 增强SVG（添加交互）
        svg_enhanced = self._add_interactivity(svg_base, knowledge_points)
        
        return svg_enhanced
    
    def _generate_mermaid(self, flow_data: List[str]) -> str:
        """生成Mermaid图表代码"""
        lines = ["graph TD"]
        
        for i, step in enumerate(flow_data):
            node_id = f"N{i}"
            next_id = f"N{i+1}"
            
            # 清理步骤文本（去掉序号）
            step_text = step.split(':', 1)[-1].strip() if ':' in step else step
            
            lines.append(f'    {node_id}["{step_text}"]')
            
            if i < len(flow_data) - 1:
                lines.append(f'    {node_id} --> {next_id}')
        
        return '\n'.join(lines)
    
    def _mermaid_to_svg(self, mermaid_code: str) -> str:
        """使用Mermaid CLI或API转换为SVG"""
        # 方案1: 使用mermaid.ink在线服务
        encoded = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
        url = f"https://mermaid.ink/svg/{encoded}"
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        
        # 方案2: 本地fallback（使用简化SVG）
        return self._generate_simple_svg(mermaid_code)
    
    def _add_interactivity(self, svg: str, knowledge_points: Dict) -> str:
        """为SVG添加交互功能"""
        # 添加点击事件、悬停提示等
        interactive_script = """
<script type="text/javascript">
<![CDATA[
  // 节点点击事件
  document.querySelectorAll('.node').forEach(node => {
    node.style.cursor = 'pointer';
    node.addEventListener('click', function(e) {
      const nodeId = this.id;
      // 触发自定义事件，前端监听
      window.dispatchEvent(new CustomEvent('node-click', {
        detail: { nodeId: nodeId }
      }));
    });
    
    node.addEventListener('mouseenter', function() {
      this.style.opacity = '0.8';
    });
    
    node.addEventListener('mouseleave', function() {
      this.style.opacity = '1';
    });
  });
]]>
</script>
"""
        
        # 在</svg>前插入脚本
        svg = svg.replace('</svg>', interactive_script + '</svg>')
        
        return svg
```

### 3. 闯关题目生成器（完整实现）

```python
# backend/app/core/question_generator/challenge_generator.py

class ChallengeQuestionGenerator:
    """三道闯关题生成器"""
    
    def __init__(self, llm_client, code_executor):
        self.llm = llm_client
        self.executor = code_executor
    
    def generate_all_challenges(self, 
                               code: str, 
                               logic_analysis: Dict) -> List[Dict]:
        """生成完整的3道闯关题"""
        challenges = []
        
        # 关卡1: 代码填空题
        challenge1 = self._generate_fill_blank(code, logic_analysis)
        challenges.append(challenge1)
        
        # 关卡2: 业务逻辑选择题
        challenge2 = self._generate_logic_choice(code, logic_analysis)
        challenges.append(challenge2)
        
        # 关卡3: 引导式复现题
        challenge3 = self._generate_guided_implementation(logic_analysis)
        challenges.append(challenge3)
        
        # 验证题目质量
        self._validate_challenges(challenges, code)
        
        return challenges
    
    def _generate_fill_blank(self, code: str, logic: Dict) -> Dict:
        """关卡1: 代码填空选择题"""
        # 选择最核心的函数
        core_function = self._select_core_function(code, logic)
        
        # 识别关键代码段
        blank_segment = self._identify_blank_segment(core_function)
        
        # 生成干扰项
        prompt = f"""
生成一道代码填空选择题。

## 完整函数代码
```python
{core_function['full_code']}
```

## 挖空位置
行 {blank_segment['start_line']} 到 {blank_segment['end_line']}

## 正确答案
```python
{blank_segment['correct_code']}
```

## 任务
1. 生成3个干扰选项，对应典型错误：
   - 选项A: 逻辑条件写反
   - 选项B: 边界值错误
   - 选项C: 循环变量误用

2. 干扰项要求：
   - 语法正确
   - 长度与正确答案相近
   - 具有迷惑性但逻辑错误

输出JSON格式：
{{
  "question": "题干描述",
  "code_with_blank": "带【______】的代码",
  "options": [
    {{"label": "A", "code": "...", "is_correct": false, "error_type": "逻辑条件反"}},
    {{"label": "B", "code": "...", "is_correct": true}},
    {{"label": "C", "code": "...", "is_correct": false, "error_type": "边界错误"}},
    {{"label": "D", "code": "...", "is_correct": false, "error_type": "变量误用"}}
  ]
}}
"""
        
        response = self.llm.generate(prompt, temperature=0.5)
        question_data = self._parse_json_response(response)
        
        # 验证：尝试执行正确答案
        self._verify_fill_blank(question_data, core_function)
        
        return {
            "level": 1,
            "type": "code_fill_blank",
            "content": question_data,
            "answer": "B",
            "explanation": self._generate_explanation(question_data)
        }
```

---

## 🗄️ 优化后的数据库设计

### 核心表结构

```sql
-- 1. 教师知识库表
CREATE TABLE teacher_knowledge_base (
    id VARCHAR(20) PRIMARY KEY,
    teacher_id VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    code_content TEXT NOT NULL,
    language VARCHAR(20) DEFAULT 'python',
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_teacher_id (teacher_id)
);

-- 2. 业务逻辑分析缓存表（独立）
CREATE TABLE business_logic_cache (
    id SERIAL PRIMARY KEY,
    problem_id VARCHAR(20) UNIQUE NOT NULL,
    code_hash VARCHAR(64) NOT NULL,          -- 代码内容的SHA256
    
    -- 5维度分析结果
    analysis_result JSONB NOT NULL,
    
    -- 可视化资源
    flow_chart_svg TEXT,
    dependency_graph_svg TEXT,
    architecture_diagram_svg TEXT,
    
    -- 知识点
    knowledge_points JSONB,
    
    -- 性能指标
    analysis_duration_ms INTEGER,
    cache_hit_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,                    -- 缓存过期时间
    
    INDEX idx_code_hash (code_hash),
    INDEX idx_problem_id (problem_id)
);

-- 3. 学生提交表
CREATE TABLE student_submissions (
    id VARCHAR(20) PRIMARY KEY,
    problem_id VARCHAR(20) NOT NULL,
    student_id VARCHAR(20) NOT NULL,
    code_content TEXT NOT NULL,
    
    -- 初步验证结果
    verification_result JSONB,
    
    -- 闯关题生成状态
    challenges_status VARCHAR(20) DEFAULT 'pending',  -- pending/generating/completed
    challenges_data JSONB,
    
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_student_problem (student_id, problem_id)
);

-- 4. 闯关答题记录表
CREATE TABLE challenge_answers (
    id SERIAL PRIMARY KEY,
    submission_id VARCHAR(20) NOT NULL,
    level INTEGER NOT NULL,                  -- 1, 2, 3
    answer JSONB NOT NULL,
    is_correct BOOLEAN,
    score INTEGER,
    feedback TEXT,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_submission (submission_id)
);

-- 5. 学习记录表（场景3使用）
CREATE TABLE learning_sessions (
    id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    source_type VARCHAR(20),                 -- file/github/text
    project_name VARCHAR(200),
    
    -- 分析结果引用
    analysis_cache_id INTEGER REFERENCES business_logic_cache(id),
    
    -- 学习进度
    learning_progress JSONB,                 -- {"completed_steps": [1,2], "current_step": 3}
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    
    INDEX idx_user_id (user_id)
);
```

---

## 🚀 私有部署方案（2026最新技术栈）

### 部署架构

```
┌────────────────────────────────────────────────────┐
│               Private Deployment                    │
├────────────────────────────────────────────────────┤
│                                                     │
│  Docker Compose (统一编排)                          │
│  ├─ Nginx (反向代理 + SSL)                         │
│  ├─ React Frontend (Vite构建)                      │
│  ├─ FastAPI Backend (Python 3.11)                  │
│  ├─ PostgreSQL 16 (主数据库)                       │
│  ├─ Redis 7.2 (缓存 + 任务队列)                    │
│  └─ Ollama + Qwen2.5-Coder-7B (本地LLM)           │
│                                                     │
│  可选组件：                                         │
│  ├─ Celery Worker (异步任务)                       │
│  ├─ Prometheus + Grafana (监控)                    │
│  └─ Portainer (容器管理)                           │
│                                                     │
└────────────────────────────────────────────────────┘
```

### 最新LLM私有部署方案

**推荐模型选择（2026年）：**

1. **Qwen2.5-Coder-7B-Instruct**（主力）
   - 专为代码理解优化
   - 7B参数，24GB显存可运行
   - 支持128K上下文窗口
   - 部署方式：Ollama

2. **DeepSeek-Coder-V2-Lite-Instruct**（备选）
   - 16B参数，性能更强
   - 需要40GB显存
   - 推理速度快

3. **Fallback方案：Claude API**
   - 当本地LLM无法处理复杂场景时
   - 仅用于关键功能（闯关题生成）
   - 按需计费

**Ollama部署配置：**

```yaml
# docker-compose.yml (LLM部分)
services:
  ollama:
    image: ollama/ollama:latest
    container_name: learnwithai-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=24h          # 模型保持加载
      - OLLAMA_NUM_GPU=1               # 使用1块GPU
      - OLLAMA_MAX_LOADED_MODELS=2     # 最多加载2个模型
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    
    # 健康检查
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**模型初始化脚本：**

```bash
#!/bin/bash
# scripts/init-ollama.sh

echo "等待Ollama服务启动..."
sleep 10

echo "下载Qwen2.5-Coder-7B模型..."
docker-compose exec ollama ollama pull qwen2.5-coder:7b-instruct

echo "测试模型..."
docker-compose exec ollama ollama run qwen2.5-coder:7b-instruct "print('Hello')"

echo "✅ LLM模型初始化完成"
```

---

### 完整docker-compose.yml

```yaml
version: '3.9'

services:
  # PostgreSQL数据库
  postgres:
    image: postgres:16-alpine
    container_name: learnwithai-db
    environment:
      POSTGRES_DB: learnwithai
      POSTGRES_USER: ${DB_USER:-admin}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
      POSTGRES_INITDB_ARGS: "-E UTF8 --locale=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-admin}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis缓存
  redis:
    image: redis:7.2-alpine
    container_name: learnwithai-redis
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  # Ollama LLM服务
  ollama:
    image: ollama/ollama:latest
    container_name: learnwithai-ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_NUM_GPU=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  # FastAPI后端
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: learnwithai-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-admin}:${DB_PASSWORD:-changeme}@postgres:5432/learnwithai
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_URL=http://ollama:11434
      - OLLAMA_MODEL=qwen2.5-coder:7b-instruct
      - SECRET_KEY=${SECRET_KEY:-your-secret-key-change-in-production}
      - CORS_ORIGINS=http://localhost:3000,http://localhost:80
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_started
    volumes:
      - ./backend:/app
      - backend_cache:/app/.cache
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    restart: unless-stopped

  # Celery Worker (异步任务)
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: learnwithai-celery
    environment:
      - DATABASE_URL=postgresql://${DB_USER:-admin}:${DB_PASSWORD:-changeme}@postgres:5432/learnwithai
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      - redis
      - postgres
      - ollama
    volumes:
      - ./backend:/app
    command: celery -A app.celery_app worker --loglevel=info --concurrency=2
    restart: unless-stopped

  # React前端
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - VITE_API_URL=${API_URL:-http://localhost:8000}
    container_name: learnwithai-frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    command: npm run dev -- --host 0.0.0.0
    restart: unless-stopped

  # Nginx反向代理
  nginx:
    image: nginx:1.25-alpine
    container_name: learnwithai-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - nginx_logs:/var/log/nginx
    depends_on:
      - backend
      - frontend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  ollama_models:
  backend_cache:
  nginx_logs:
```

---

## 📁 优化后的完整目录结构

```
learnwithai/
├── docker-compose.yml
├── .env.example
├── README.md
├── DEPLOYMENT.md                    # 部署文档
│
├── frontend/                        # 前端 (React + TypeScript + Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/              # 通用组件
│   │   │   │   ├── CodeEditor.tsx
│   │   │   │   ├── LoadingSpinner.tsx
│   │   │   │   └── SVGViewer.tsx
│   │   │   ├── teacher/             # 教师端组件
│   │   │   │   ├── ProblemUpload.tsx
│   │   │   │   └── KnowledgeBase.tsx
│   │   │   ├── student/             # 学生端组件
│   │   │   │   ├── ProblemView.tsx
│   │   │   │   ├── ChallengeQuiz.tsx
│   │   │   │   └── ResultReport.tsx
│   │   │   └── learning/            # 学习端组件
│   │   │       ├── ProjectUpload.tsx
│   │   │       ├── InteractiveFlowChart.tsx
│   │   │       ├── KnowledgePointsPanel.tsx
│   │   │       └── LearningPathGuide.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx         # 主页（学习端入口）
│   │   │   ├── TeacherDashboard.tsx
│   │   │   ├── StudentDashboard.tsx
│   │   │   └── LearningPlatform.tsx
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── teacher.ts
│   │   │   ├── student.ts
│   │   │   └── learning.ts
│   │   ├── store/
│   │   │   └── useStore.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   │       ├── codeHighlight.ts
│   │       └── svgInteraction.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── backend/                         # 后端 (FastAPI + Python)
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── teacher.py       # 教师端API
│   │   │       ├── student.py       # 学生端API
│   │   │       └── learning.py      # 学习端API
│   │   ├── core/                    # 核心业务逻辑
│   │   │   ├── business_logic_analyzer/    # 【核心模块】
│   │   │   │   ├── __init__.py
│   │   │   │   ├── parser/
│   │   │   │   │   ├── ast_parser.py
│   │   │   │   │   ├── code_structure.py
│   │   │   │   │   └── dependency_analyzer.py
│   │   │   │   ├── analyzer/
│   │   │   │   │   ├── logic_decomposer.py      # 5维度拆解
│   │   │   │   │   ├── flow_analyzer.py
│   │   │   │   │   └── knowledge_extractor.py
│   │   │   │   ├── visualizer/
│   │   │   │   │   ├── svg_generator.py
│   │   │   │   │   ├── mermaid_adapter.py
│   │   │   │   │   └── interactive_enhancer.py
│   │   │   │   └── llm/
│   │   │   │       ├── prompt_templates.py
│   │   │   │       ├── ollama_client.py
│   │   │   │       └── response_parser.py
│   │   │   ├── question_generator/
│   │   │   │   ├── challenge_generator.py       # 闯关题生成
│   │   │   │   ├── validator.py
│   │   │   │   └── difficulty_adjuster.py
│   │   │   └── code_verifier/
│   │   │       ├── syntax_checker.py
│   │   │       ├── test_executor.py
│   │   │       └── logic_comparator.py
│   │   ├── models/                  # 数据模型 (SQLAlchemy)
│   │   │   ├── teacher.py
│   │   │   ├── student.py
│   │   │   ├── problem.py
│   │   │   └── analysis_cache.py
│   │   ├── schemas/                 # Pydantic Schemas
│   │   │   ├── teacher.py
│   │   │   ├── student.py
│   │   │   └── learning.py
│   │   ├── services/                # 业务服务层
│   │   │   ├── teacher_service.py
│   │   │   ├── student_service.py
│   │   │   └── learning_service.py
│   │   ├── tasks/                   # Celery异步任务
│   │   │   ├── analysis_tasks.py
│   │   │   └── question_tasks.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── config.py
│   │   ├── celery_app.py
│   │   └── main.py
│   ├── tests/
│   │   ├── test_analyzer.py
│   │   ├── test_generator.py
│   │   └── test_api.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf
│   └── ssl/                         # SSL证书
│
├── scripts/
│   ├── init-ollama.sh              # 初始化LLM模型
│   ├── init-db.sql                 # 初始化数据库
│   ├── backup.sh                   # 数据备份脚本
│   └── deploy.sh                   # 一键部署脚本
│
└── docs/
    ├── API.md                       # API文档
    ├── ARCHITECTURE.md              # 架构文档
    ├── DEPLOYMENT.md                # 部署指南
    ├── USER_GUIDE.md                # 用户手册
    └── TEACHER_GUIDE.md             # 教师手册
```

---

## 🎯 实施路线图（16周）

### Phase 1: 核心引擎开发（Week 1-6）

#### Week 1-2: 业务逻辑分析引擎
- [ ] AST解析器实现（Tree-sitter）
- [ ] 5维度拆解逻辑
- [ ] LLM集成（Ollama + Qwen2.5-Coder）
- [ ] 单元测试（10个测试用例）

#### Week 3-4: 可视化生成器
- [ ] Mermaid流程图生成
- [ ] SVG交互增强
- [ ] 知识点标注系统
- [ ] 前端SVG展示组件

#### Week 5-6: 闯关题生成器
- [ ] 3种题型生成逻辑
- [ ] 双Agent验证机制
- [ ] 题目质量评估
- [ ] 批量生成测试

**里程碑1：** 核心引擎能独立工作，输入代码→输出分析结果+题目

---

### Phase 2: 三端应用开发（Week 7-12）

#### Week 7-8: 教师上传端
- [ ] 文件上传接口
- [ ] 知识库管理
- [ ] 简洁UI界面
- [ ] 批量上传支持

#### Week 9-10: 学生答题端
- [ ] 题目展示页面
- [ ] 答案提交与验证
- [ ] 闯关题答题界面
- [ ] 评分与反馈系统

#### Week 11-12: 学习探索端（主页面）
- [ ] 项目上传（文件/GitHub）
- [ ] 交互式流程图展示
- [ ] 知识点面板
- [ ] 学习路径推荐

**里程碑2：** 三端功能打通，完整流程可演示

---

### Phase 3: 优化与测试（Week 13-14）

#### Week 13: 性能优化
- [ ] 缓存策略优化
- [ ] LLM响应加速
- [ ] 数据库查询优化
- [ ] 前端性能优化

#### Week 14: 真实测试
- [ ] 小班试用（10-20人）
- [ ] 收集用户反馈
- [ ] Bug修复
- [ ] 用户体验优化

**里程碑3：** 系统稳定，用户满意度>80%

---

### Phase 4: 部署与答辩（Week 15-16）

#### Week 15: 部署准备
- [ ] Docker镜像优化
- [ ] 部署文档完善
- [ ] 监控告警配置
- [ ] 演示环境搭建

#### Week 16: 答辩材料
- [ ] 5分钟演示视频
- [ ] 20页PPT
- [ ] 技术博客
- [ ] 开源仓库发布

**最终交付：** 完整可部署系统 + 演示材料 + 文档

---

## 📊 关键创新点

### 1. 独立的业务逻辑分析引擎
- **创新：** 将分析能力抽象为独立模块，可复用于多种场景
- **技术：** AST静态分析 + LLM语义理解混合方案
- **优势：** 比纯LLM准确，比纯规则灵活

### 2. 三端分离的应用架构
- **创新：** 教师端极简化，学生端功能丰富，学习端独立存在
- **优势：** 各端专注核心功能，用户体验更好

### 3. 交互式SVG流程图
- **创新：** 不是静态图片，而是可点击、可展开的学习工具
- **技术：** Mermaid + 自定义SVG增强
- **优势：** 学生可以边看图边学代码

### 4. 延迟分析策略
- **创新：** 教师上传时不分析，学生首次访问时才分析
- **优势：** 节省计算资源，避免重复分析

### 5. 私有化部署友好
- **创新：** 完全基于开源组件，无外部API依赖
- **技术：** Ollama本地LLM + Docker容器化
- **优势：** 学校可完全内网部署，数据不出校园

---

## 💡 技术难点与解决方案

### 难点1：LLM在CPU环境下推理速度慢

**问题：** 学校可能没有GPU服务器

**解决方案：**
1. 使用量化模型（GGUF格式，Q4_K_M量化）
2. 实现智能缓存（相似代码复用分析结果）
3. 异步任务队列（Celery），前端显示进度

### 难点2：大型项目分析性能

**问题：** 上万行代码解析可能超时

**解决方案：**
1. 智能文件筛选（只分析核心文件）
2. 增量分析（Git diff，只分析改动部分）
3. 分布式解析（多Worker并行）

### 难点3：闯关题质量保证

**问题：** LLM生成的题目可能不符合要求

**解决方案：**
1. Few-shot Prompt（提供优质示例）
2. 结构化输出（JSON Schema约束）
3. 多轮验证（生成→执行→检查→重生成）
4. 人工审核机制（教师可修改）

---

## 🎓 成功指标

| 阶段 | 指标 | 目标值 | 衡量方式 |
|-----|------|--------|---------|
| MVP | 核心功能完整度 | 100% | 三端基本流程打通 |
| MVP | 分析准确率 | >85% | 人工评审50个样本 |
| Beta | 闯关题质量 | >80% | 教师满意度评分 |
| Beta | 系统响应时间 | <60s | 从上传到生成题目 |
| 最终 | 用户满意度 | NPS>7 | 问卷调查 |
| 最终 | 系统稳定性 | 无重大Bug | 连续运行7天 |

---

## 📞 资源与参考

### 技术参考
- [Tree-sitter官方文档](https://tree-sitter.github.io/)
- [Qwen2.5-Coder模型](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
- [Ollama部署指南](https://github.com/ollama/ollama)
- [Mermaid流程图语法](https://mermaid.js.org/)

### 学术论文
- AutoMCQ: 自动生成代码理解题 ([arXiv](https://arxiv.org/html/2505.16430v1))
- CODE-GEN: 双Agent生成验证 ([arXiv](https://arxiv.org/html/2604.03926))

### 开源项目
- [codegraph-gen](https://pypi.org/project/codegraph-gen/) - 代码知识图谱
- [WorkBuddy架构图绘制](https://www.cnblogs.com/getmoon/p/22066357) - SVG生成参考

---

## 📝 版本信息

- **文档版本：** V2.0
- **更新日期：** 2026年1月
- **作者：** LearnWithAI项目组
- **许可证：** MIT License

---

## ✅ 优化总结

### 与V1.0相比的主要改进：

1. **架构优化**
   - ✅ 业务逻辑分析引擎独立化
   - ✅ 三端分离（教师/学生/学习）
   - ✅ 延迟分析策略

2. **功能增强**
   - ✅ 新增核心学习端（主页面功能）
   - ✅ 交互式SVG流程图
   - ✅ 知识点智能标注
   - ✅ 学习路径推荐

3. **技术升级**
   - ✅ 采用2026年最新LLM（Qwen2.5-Coder）
   - ✅ 完全私有化部署方案
   - ✅ 智能缓存机制
   - ✅ GPU/CPU双支持

4. **用户体验**
   - ✅ 教师端极简化（仅上传功能）
   - ✅ 学生端完整闯关流程
   - ✅ 学习端独立使用（无需题目背景）

---

## 📋 V2.0 完整版特别说明

### 本版本的核心改进

本 V2.0 完整版在原有基础上，整合了以下重要内容：

#### 1. 从 V2.1 提取的有价值内容
- ✅ **更严格的 MVP 定义**：明确了什么在范围内，什么不在
- ✅ **量化验收指标**：从模糊描述到具体数字（如解析成功率 ≥98%）
- ✅ **详细的安全威胁模型**：沙箱执行、SSRF 防护、提示注入防护
- ✅ **完整的数据模型设计**：PostgreSQL 表结构、索引、约束
- ✅ **异步任务管理**：job_id、SSE 状态订阅、错误分类
- ✅ **真实难点分析表**：不回避问题，给出实际解决方案
- ✅ **测试分层策略**：从单元测试到安全测试的完整覆盖
- ✅ **离线部署方案**：内网环境的实际部署考量

#### 2. 保留的原创内容
- ✅ 基于真实 GitHub 项目的技术选型
- ✅ 完整的前端 UI 设计（Vue 3 代码示例）
- ✅ 详细的实施时间表（16 周分解到每周）
- ✅ 开源项目清单（所有链接均可访问）

### 文档适用对象

**主要读者**：
- 项目开发团队（技术实施指南）
- 项目管理者（进度和资源规划）
- 答辩评审专家（完整的技术方案）
- 投资方/合作方（可行性评估）

**次要读者**：
- 教育技术研究者（参考案例）
- 开源贡献者（技术选型参考）

### 与其他版本的关系

```
V1.0（概念版）
  ↓
V2.0（完整实施版）← 你现在看到的版本
  ↑ 
V2.1（深度实施版，GPT-6 编写）
```

**说明**：V2.0 是主版本，已从 V2.1 中提取了所有有价值的内容并整合。

---

## 🎯 项目成功的关键因素

### 技术层面
1. ✅ **Tree-sitter 解析质量**：Python 样本 ≥98% 成功率
2. ✅ **LLM 本地部署稳定性**：Ollama/vLLM 正常运行
3. ✅ **沙箱安全性**：0 次逃逸成功
4. ✅ **缓存策略**：减少重复计算，提升响应速度

### 教育层面
1. ✅ **教师参与度**：愿意审核和改进分析结果
2. ✅ **学生接受度**：认可这种学习方式
3. ✅ **题目质量**：≥90% 的题目无需修改即可发布
4. ✅ **学习效果验证**：通过前后测量化改进

### 运维层面
1. ✅ **部署成功率**：在标准环境 ≥95%
2. ✅ **系统稳定性**：连续运行 7 天无重大故障
3. ✅ **备份可恢复性**：演练环境成功恢复
4. ✅ **文档完整性**：新人可按文档完成部署

---

## 💡 给实施团队的建议

### 开发阶段
1. **先做 MVP，不要贪大求全**
   - 第一期只做 Python
   - 先支持小文件（< 1000 行）
   - UI 简洁实用即可

2. **建立金标准数据集**
   - 至少 30 个真实题目
   - 教师和开发者独立标注
   - 持续更新和改进

3. **安全第一**
   - 代码沙箱从第一天就要做对
   - 不要等到最后才考虑安全
   - 每个版本都要跑安全测试

### 测试阶段
1. **小范围试点**
   - 10-20 名学生
   - 1-2 名教师
   - 收集详细反馈

2. **关注真实体验**
   - 等待时间是否可接受
   - 错误提示是否清晰
   - 学习路径是否流畅

### 部署阶段
1. **准备充分再上线**
   - 完整的备份恢复演练
   - 故障预案和回滚方案
   - 24 小时内响应机制

2. **渐进式推广**
   - 先一个班级
   - 再一个学院
   - 最后全校推广

---

## 🚀 下一步行动计划

### 立即行动（第 1 周）
1. [ ] 创建 GitHub 仓库（公开或私有）
2. [ ] 初始化项目结构（参考第十五章目录结构）
3. [ ] 搭建开发环境（Docker、PostgreSQL、Redis）
4. [ ] 验证 Tree-sitter Python 解析（用 5 个样本测试）
5. [ ] 编写项目 README 和 CONTRIBUTING

### 短期目标（第 2-4 周）
1. [ ] 实现安全输入模块（压缩包检查、SHA-256）
2. [ ] 完成 Python AST 解析器
3. [ ] 建立初步的调用图生成
4. [ ] 搭建 FastAPI 基础框架
5. [ ] 设计数据库 Schema

### 中期目标（第 5-12 周）
1. [ ] 集成 Ollama 本地 LLM
2. [ ] 实现流程图生成（React Flow）
3. [ ] 完成三道闯关题生成器
4. [ ] 开发代码沙箱执行环境
5. [ ] 构建教师端和学生端 UI

### 长期目标（第 13-16 周）
1. [ ] 金标准评测并达标
2. [ ] 安全测试和性能优化
3. [ ] 小班试用并收集反馈
4. [ ] 准备演示和答辩材料
5. [ ] 编写完整文档

---

## 📞 联系与贡献

### 如何贡献
- 🐛 **报告 Bug**：通过 GitHub Issues
- 💡 **功能建议**：通过 GitHub Discussions
- 🔧 **代码贡献**：通过 Pull Request
- 📖 **文档改进**：直接提交 PR

### 社区支持
- GitHub 仓库：[待创建]
- 技术文档：[待发布]
- 演示视频：[待录制]

---

## 📚 相关资源链接汇总

**核心开源项目**：
- [Tree-sitter](https://github.com/tree-sitter/tree-sitter) - 增量解析器
- [Mermaid](https://github.com/mermaid-js/mermaid) - 图表生成
- [FastAPI](https://github.com/tiangolo/fastapi) - Python Web 框架
- [Ollama](https://github.com/ollama/ollama) - 本地 LLM 运行
- [React Flow](https://github.com/xyflow/xyflow) - 交互式流程图

**参考论文**：
- [Chatbot-Based Assessment of Code Understanding](https://arxiv.org/html/2604.07304)
- [A Framework for Concept-Based Quiz Generation](https://arxiv.org/html/2503.14662v1)

**部署参考**：
- [FastAPI Full Stack Template](https://github.com/orlan0045/full-stack-fastapi-vue-simplified)
- [Docker PostgreSQL Redis Boilerplate](https://github.com/adityarizqi/Docker-PostgreSQL-Redis-Boilerplate)

---

## 🙏 致谢

本方案的形成得益于：
- **开源社区**：Tree-sitter、Mermaid、FastAPI、Vue 等优秀项目
- **教育工作者**：提供真实需求和教学场景反馈
- **技术专家**：代码审查和架构建议
- **学生用户**：真实使用体验和改进建议

特别感谢所有为教育技术进步做出贡献的人们！

---

**📄 文档结束**

*LearnWithAI - 让业务逻辑理解成为编程教育的核心*

*Version 2.0 | 2026年1月 | MIT License*

---

*本文档为LearnWithAI项目的完整实施方案，涵盖需求分析、技术选型、架构设计、实施计划等所有内容。*
