<script setup lang="ts">
import { computed } from 'vue'
import { getRecipeFoodIcon } from '../utils/recipeFoodIcon'

const props = defineProps<{
  title?: string | null
  ingredients?: Array<string | { name?: string }> | null
}>()

const icon = computed(() => getRecipeFoodIcon(props.title, props.ingredients))
</script>

<template>
  <div
    class="recipe-food-icon"
    :style="{ background: icon.bg }"
    aria-hidden="true"
  >
    <img
      class="recipe-food-icon-img"
      :src="icon.src"
      :alt="''"
      draggable="false"
    >
  </div>
</template>

<style scoped>
.recipe-food-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: inherit;
  overflow: hidden;
}
.recipe-food-icon-img {
  width: 78%;
  height: 78%;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
}
</style>
