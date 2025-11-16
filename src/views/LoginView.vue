<script setup lang="ts">
import LogoImage from '@/assets/logo.png';
import { useLoginStore } from '@/stores/login';
import { Lock, User } from '@element-plus/icons-vue';
import type { FormInstance, FormRules } from 'element-plus';
import { ElButton, ElForm, ElFormItem, ElInput, ElMessage } from 'element-plus';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { checkHealth } from '@/utils/api';

// 获取环境变量
const env = import.meta.env;
const icpNumber = env.VITE_ICP_NUMBER;
const policeNumber = env.VITE_POLICE_NUMBER;
const policeString = env.VITE_POLICE_STRING;
const companyName = env.VITE_COMPANY_NAME;

const router = useRouter();
const loginStore = useLoginStore();

// 表单数据
const loginForm = ref({
  username: '',
  password: '',
});

// 表单规则
const rules = ref<FormRules>({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度应为 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 30, message: '长度应为 6 到 30 个字符', trigger: 'blur' }
  ]
});

const formRef = ref<FormInstance>();
const loading = ref(false);

// 登录方法
const handleLogin = async (formEl?: FormInstance) => {
  if (!formEl) return;

  try {
    await checkHealth();
  } catch (error) {
    console.error('健康检查失败:', error);
    ElMessage.error('无法连接到服务器，请稍后再试');
    return;
  }

  await formEl.validate(async (valid, fields) => {
    if (!valid) {
      console.error('表单验证失败:', fields);
      return;
    }

    loading.value = true;
    try {
      await loginStore.login(loginForm.value.username, loginForm.value.password);
      ElMessage.success('登录成功');
      router.push('/dashboard');
    } catch (error) {
      console.error('登录失败:', error);
      ElMessage.error('登录失败，请检查用户名和密码');
    } finally {
      loading.value = false;
    }
  });
};
</script>

<template>
  <div class="login-container">
    <div class="login-box">
      <div class="logo-container">
        <img :src="LogoImage" alt="Logo" class="logo" />
      </div>
      <h2 class="title">DataForge</h2>
      <h3 class="sub-title">智能数据锻造平台</h3>
      <el-form
        ref="formRef"
        :model="loginForm"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin(formRef)">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            :prefix-icon="User"
            placeholder="用户名"
            type="text"
            tabindex="1"
            size="large"
            clearable
            autofocus />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            :prefix-icon="Lock"
            placeholder="密码"
            type="password"
            tabindex="2"
            size="large"
            show-password />
        </el-form-item>

        <el-button
          :loading="loading"
          type="primary"
          size="large"
          class="login-button"
          @click="handleLogin(formRef)">
          {{ loading ? '登录中...' : '登录' }}
        </el-button>
      </el-form>
    </div>

    <!-- 备案信息 -->
    <div class="beian" v-if="icpNumber || (policeNumber && policeString)">
      <div class="beian-links">
        <template v-if="icpNumber">
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
            {{ icpNumber }}
          </a>
        </template>
        <template v-if="icpNumber && (policeNumber && policeString)">
          <span class="divider">|</span>
        </template>
        <template v-if="policeNumber && policeString">
          <img src="//www.beian.gov.cn/img/ghs.png" alt="公安备案图标" class="beian-icon" />
          <a :href="`http://www.beian.gov.cn/#/query/webSearch?code=${policeNumber}`" rel="noreferrer" target="_blank">
            {{ policeString }}
          </a>
        </template>
      </div>
      <template v-if="companyName">
        <div class="company-info">
          © {{ new Date().getFullYear() }} {{ companyName }}
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  height: 100vh;
  width: 100vw;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  overflow: hidden;
}

.login-box {
  width: 400px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: transform 0.3s ease;
}

.login-box:hover {
  transform: translateY(-5px);
}

.logo-container {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.logo {
  width: 80px;
  height: 80px;
  object-fit: contain;
}

.title {
  text-align: center;
  font-size: 32px;
  color: #1e293b;
  margin-bottom: 8px;
  font-weight: 600;
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.sub-title {
  text-align: center;
  font-size: 16px;
  color: #475569;
  margin-bottom: 36px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.login-form {
  .el-input {
    background: transparent;

    :deep(.el-input__wrapper) {
      background: transparent;
      box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.1);
      border-radius: 8px;
      padding: 0 12px;

      &.is-focus {
        box-shadow: 0 0 0 1px #3b82f6;
      }

      &:hover {
        box-shadow: 0 0 0 1px #3b82f6;
      }
    }
  }
}

.login-button {
  width: 100%;
  border-radius: 8px;
  margin-top: 20px;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  border: none;
  height: 44px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 1px;
  transition: all 0.3s ease;
}

.login-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.login-button:active {
  transform: translateY(0);
}

/* 备案信息样式 */
.beian {
  position: fixed;
  bottom: 20px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 14px;
  color: #64748b;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.beian-links {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  gap: 4px;
}

.beian a {
  color: #64748b;
  text-decoration: none;
  transition: color 0.3s ease;
  white-space: nowrap;
}

.beian a:hover {
  color: #3b82f6;
}

.beian .divider {
  margin: 0 6px;
  color: #94a3b8;
}

.beian .beian-icon {
  height: 14px;
  margin-right: 4px;
  vertical-align: middle;
  position: relative;
  top: -1px;
}

.beian .company-info {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
</style>
