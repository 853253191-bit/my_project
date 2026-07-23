<template>
  <div v-if="sources.length" class="sources-list">
    <strong>参考来源：</strong>
    <ul>
      <li v-for="s in sources" :key="s.id">
        <a v-if="s.source_url" :href="s.source_url" target="_blank">{{ s.title }}</a>
        <span v-else>{{ s.title }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { RecipeSource } from '../api/client'

defineProps<{
  sources: RecipeSource[]
}>()
</script>

<style scoped>
ul {
  list-style: none;
  margin-top: 4px;
}
li {
  padding: 2px 0;
}
</style>
