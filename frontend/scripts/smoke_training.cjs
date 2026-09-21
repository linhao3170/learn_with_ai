const fs = require('fs');
const path = require('path');

// Minimal ref/computed shim for smoke-testing TrainingView script logic outside the browser.
function ref(v) {
  let val = v;
  return { get value() { return val; }, set value(nv) { val = nv; } };
}
function computed(fn) {
  return { get value() { return fn(); } };
}

const vueSrc = fs.readFileSync(path.join(__dirname, '..', 'src', 'views', 'TrainingView.vue'), 'utf8');
const m = vueSrc.match(/<script setup>([\s\S]*?)<\/script>/);
if (!m) { console.error('NO SCRIPT'); process.exit(1); }

const mockData = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'public', 'demo', 'project_analysis.json'), 'utf8')
);

let script = m[1];
script = script.replace(/import .*?\n/g, '');
script = script.replace(/const emit = defineEmits\([^)]*\)\s*\n?/, '');
script = script.replace(
  /const questions = ref\(\[\]\)/,
  `const questions = ref(${JSON.stringify(mockData.training.questions)})`
);
script = script.replace(
  /const projectModules = ref\(\[\]\)/,
  `const projectModules = ref(${JSON.stringify(mockData.modules)})`
);
script = script.replace(
  /const coreFlow = ref\(null\)/,
  `const coreFlow = ref(${JSON.stringify(mockData.core_flows[0])})`
);
script = script.replace(
  /onMounted\(async \(\) => \{[\s\S]*?\}\)\s*\n?/,
  ''
);

const code = `
${script}
return { currentLevel, currentView, progressPercent, level1Correct, level2Correct, level3Correct, level4Correct,
  finalScore, scoreLevel, projectModules, coreFlow,
  submitLevel1, submitLevel2, submitLevel3, submitLevel4,
  nextLevel, prevLevel, goToResult, goBackToLevel4, restart,
  selectedLevel1, selectedLevel2, selectedLevel3, selectedLevel4 };
`;

// eslint-disable-next-line no-new-func
const ctx = (new Function('ref', 'computed', 'onMounted', code))(ref, computed, () => {});

function log(label, ...v) {
  console.log(`[${label}]`, ...v);
}

log('init', 'level=' + ctx.currentLevel.value, 'view=' + ctx.currentView.value, 'progress=' + ctx.progressPercent.value);

ctx.selectedLevel1.value = ['A','C','D','H'];
ctx.submitLevel1();
log('L1', 'correct=' + ctx.level1Correct.value);

ctx.nextLevel();
log('after L1 next', 'level=' + ctx.currentLevel.value);

ctx.selectedLevel2.value = 'A';
ctx.submitLevel2();
ctx.nextLevel();
log('L2', 'correct=' + ctx.level2Correct.value, 'level=' + ctx.currentLevel.value);

ctx.selectedLevel3.value = 'A';
ctx.submitLevel3();
ctx.nextLevel();
log('L3', 'correct=' + ctx.level3Correct.value, 'level=' + ctx.currentLevel.value);

ctx.selectedLevel4.value = 'D';
ctx.submitLevel4();
log('L4', 'correct=' + ctx.level4Correct.value);

ctx.goToResult();
log('result', 'view=' + ctx.currentView.value, 'progress=' + ctx.progressPercent.value,
  'finalScore=' + ctx.finalScore.value, 'level=' + ctx.scoreLevel.value.label,
  'modules=' + ctx.projectModules.value.length, 'flow=' + ctx.coreFlow.value.name);

ctx.goBackToLevel4();
log('back', 'view=' + ctx.currentView.value, 'level=' + ctx.currentLevel.value);

ctx.restart();
log('restart', 'view=' + ctx.currentView.value, 'level=' + ctx.currentLevel.value);
