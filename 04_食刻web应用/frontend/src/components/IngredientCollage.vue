<script setup lang="ts">
import { computed } from 'vue'
import {
  DEFAULT_INGREDIENT_ICON,
  getIngredientIcon,
  pickIngredientNames,
} from '../utils/ingredientIcons'

const props = withDefaults(
  defineProps<{
    ingredients?: Array<string | { name?: string }> | null
    /** 最多展示几个食材图标 */
    max?: number
    /** 圆形图标尺寸（px）；fill 模式下忽略，按容器自适应 */
    iconSize?: number
    /** 叠放并撑满父容器 */
    fill?: boolean
  }>(),
  { max: 3, iconSize: 48, fill: false },
)

/** 取前 N 个食材；为空时用默认占位 */
const displayIcons = computed(() => {
  const names = pickIngredientNames(props.ingredients, props.max)
  if (!names.length) {
    return [{ key: 'default', icon: DEFAULT_INGREDIENT_ICON, label: '默认' }]
  }
  return names.map((name, i) => ({
    key: `${name}-${i}`,
    icon: getIngredientIcon(name),
    label: name,
  }))
})

const count = computed(() => displayIcons.value.length)

const circleStyle = computed(() => {
  if (props.fill) return {}
  return {
    width: `${props.iconSize}px`,
    height: `${props.iconSize}px`,
    fontSize: `${Math.round(props.iconSize * 0.58)}px`,
  }
})
</script>

<template>
  <div
    class="ingredient-collage"
    :class="{ fill, [`count-${count}`]: true }"
    aria-hidden="true"
  >
    <span
      v-for="(item, idx) in displayIcons"
      :key="item.key"
      class="ingredient-icon"
      :style="{ ...circleStyle, zIndex: idx + 1 }"
      :title="item.label"
    >{{ item.icon }}</span>
  </div>
</template>

<style scoped>
.ingredient-collage {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ingredient-collage:not(.fill) {
  gap: 0;
}
.ingredient-collage:not(.fill) .ingredient-icon + .ingredient-icon {
  margin-left: -10px;
}

/* 撑满父级色块，大图标叠放 */
.ingredient-collage.fill {
  width: 100%;
  height: 100%;
  position: relative;
}
.ingredient-collage.fill .ingredient-icon {
  width: 62%;
  height: 62%;
  font-size: clamp(28px, 38%, 52px);
  margin-left: -14%;
  box-shadow:
    0 4px 12px rgba(120, 80, 40, 0.12),
    inset 0 0 0 2px rgba(255, 255, 255, 0.55);
}
.ingredient-collage.fill .ingredient-icon:first-child {
  margin-left: 0;
}
/* 1 个：居中放大 */
.ingredient-collage.fill.count-1 .ingredient-icon {
  width: 72%;
  height: 72%;
  font-size: clamp(36px, 48%, 64px);
  margin-left: 0;
}
/* 2 个：略大、明显叠放 */
.ingredient-collage.fill.count-2 .ingredient-icon {
  width: 66%;
  height: 66%;
  margin-left: -18%;
  font-size: clamp(32px, 42%, 56px);
}
.ingredient-collage.fill.count-2 .ingredient-icon:first-child {
  margin-left: 0;
}

.ingredient-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #fff8f0;
  line-height: 1;
  position: relative;
  flex-shrink: 0;
  box-shadow:
    0 2px 8px rgba(120, 80, 40, 0.1),
    inset 0 0 0 1px rgba(160, 120, 80, 0.1);
}
</style>
