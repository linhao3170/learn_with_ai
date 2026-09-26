<template>
  <div v-if="open" class="fixed inset-0 z-[80] flex items-center justify-center px-4" data-test="login-dialog">
    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="close"></div>
    <section class="relative w-full max-w-md glass-card p-6 md:p-7 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <button class="absolute right-4 top-4 text-gray-500 hover:text-white" aria-label="关闭登录窗口" @click="close">×</button>
      <div class="text-[10px] font-mono tracking-[0.3em] text-neon-blue uppercase mb-2">LearnWithAI · Account</div>
      <h2 id="login-title" class="text-2xl font-bold text-white">登录工作区</h2>
      <p class="text-xs text-gray-400 mt-2 leading-relaxed">登录信息只保存在当前浏览器，用于恢复你的项目与学习进度。当前版本没有接入远程账号服务。</p>

      <form class="mt-6 space-y-4" @submit.prevent="submit">
        <label class="block">
          <span class="text-xs text-gray-400">用户名</span>
          <input v-model.trim="username" autofocus autocomplete="username" class="login-input mt-1" placeholder="例如：student" data-test="login-username" />
        </label>
        <label class="block">
          <span class="text-xs text-gray-400">密码</span>
          <input v-model="password" type="password" autocomplete="current-password" class="login-input mt-1" placeholder="至少 4 位（演示模式）" data-test="login-password" />
        </label>
        <p v-if="error" class="text-xs text-red-300" data-test="login-error">{{ error }}</p>
        <button class="w-full rounded-xl py-3 text-sm font-medium text-white bg-gradient-to-r from-neon-blue to-neon-purple hover:shadow-lg hover:shadow-neon-blue/20 transition-all" data-test="login-submit">登录并继续</button>
      </form>

      <button class="mt-3 w-full rounded-xl py-2.5 text-xs text-gray-400 border border-deep-border hover:text-white hover:border-neon-blue/30 transition-colors" data-test="login-guest" @click="$emit('guest')">以游客身份继续</button>
      <div class="mt-4 text-[10px] text-gray-600 leading-relaxed">演示账号不会发送到服务器，也不会改变业务逻辑分析结果。</div>
    </section>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['close', 'submit', 'guest'])
const username = ref('')
const password = ref('')
const error = ref('')

watch(() => props.open, (open) => {
  if (open) error.value = ''
})

function close() { emit('close') }
function submit() {
  if (!username.value) { error.value = '请输入用户名'; return }
  if (password.value.length < 4) { error.value = '密码至少需要 4 位'; return }
  emit('submit', { username: username.value })
}
</script>

