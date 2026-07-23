<script setup lang="ts">
import { computed } from 'vue'
import { getArtVariant, getCuisineGradient } from '../utils/dishArt'

const props = withDefaults(
  defineProps<{
    title: string
    cuisine?: string | null
    size?: number
    /** 铺满父容器（用于今日推荐等横向卡片顶栏） */
    fill?: boolean
  }>(),
  { size: 80, fill: false },
)

const variant = computed(() => getArtVariant(props.title))
const gradient = computed(() => getCuisineGradient(props.cuisine))
const boxStyle = computed(() => {
  const base = { background: gradient.value }
  if (props.fill) {
    return { ...base, width: '100%', height: '100%' }
  }
  return {
    ...base,
    width: `${props.size}px`,
    height: `${props.size}px`,
  }
})
</script>

<template>
  <div
    class="dish-art"
    :class="{ fill }"
    :style="boxStyle"
    aria-hidden="true"
  >
    <!-- 变体 0：大圆（右下）+ 小三角（左上） -->
    <template v-if="variant === 0">
      <span class="shape shape-circle shape-lg pos-br" />
      <span class="shape shape-tri shape-sm pos-tl" />
    </template>

    <!-- 变体 1：大三角（右下）+ 圆环（左上） -->
    <template v-else-if="variant === 1">
      <span class="shape shape-tri shape-lg pos-br" />
      <span class="shape shape-ring shape-md pos-tl" />
    </template>

    <!-- 变体 2：大圆环（右上）+ 小圆（左下） -->
    <template v-else-if="variant === 2">
      <span class="shape shape-ring shape-lg pos-tr" />
      <span class="shape shape-circle shape-sm pos-bl" />
    </template>

    <!-- 变体 3：三点阵（右下）+ 三角（左上） -->
    <template v-else>
      <span class="shape shape-dots pos-br">
        <i /><i /><i />
      </span>
      <span class="shape shape-tri shape-sm pos-tl" />
    </template>
  </div>
</template>

<style scoped>
.dish-art {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  flex-shrink: 0;
}
.dish-art.fill {
  border-radius: 0;
}

.shape {
  position: absolute;
  pointer-events: none;
}

/* ===== 圆形 ===== */
.shape-circle {
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
}
.shape-circle.shape-lg {
  width: 58%;
  height: 58%;
  background: rgba(255, 255, 255, 0.28);
}
.shape-circle.shape-sm {
  width: 28%;
  height: 28%;
  background: rgba(255, 255, 255, 0.45);
}

/* ===== 三角形（clip-path） ===== */
.shape-tri {
  background: rgba(255, 255, 255, 0.4);
  clip-path: polygon(50% 8%, 92% 88%, 8% 88%);
}
.shape-tri.shape-lg {
  width: 62%;
  height: 62%;
  background: rgba(255, 255, 255, 0.32);
}
.shape-tri.shape-sm {
  width: 32%;
  height: 32%;
  background: rgba(255, 255, 255, 0.48);
}

/* ===== 圆环 ===== */
.shape-ring {
  border-radius: 50%;
  background: transparent;
  border: 6px solid rgba(255, 255, 255, 0.38);
  box-sizing: border-box;
}
.shape-ring.shape-lg {
  width: 56%;
  height: 56%;
  border-width: 7px;
  border-color: rgba(255, 255, 255, 0.3);
}
.shape-ring.shape-md {
  width: 34%;
  height: 34%;
  border-width: 5px;
  border-color: rgba(255, 255, 255, 0.45);
}

/* ===== 点阵 ===== */
.shape-dots {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
  width: 42%;
  height: 42%;
}
.shape-dots i {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.42);
}
.shape-dots i:nth-child(3) {
  grid-column: 1 / 2;
  background: rgba(255, 255, 255, 0.28);
}

/* ===== 位置 ===== */
.pos-tl {
  top: 10%;
  left: 10%;
}
.pos-tr {
  top: 8%;
  right: 8%;
}
.pos-bl {
  bottom: 12%;
  left: 12%;
}
.pos-br {
  bottom: 6%;
  right: 6%;
}
</style>
