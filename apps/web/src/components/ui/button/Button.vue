<script setup lang="ts">
import { computed, useAttrs } from "vue";

import { cn } from "@/lib/utils";

import { buttonVariants, type ButtonSize, type ButtonVariant } from "./button";

defineOptions({
  inheritAttrs: false
});

const props = withDefaults(
  defineProps<{
    class?: string;
    size?: ButtonSize;
    type?: "button" | "submit" | "reset";
    variant?: ButtonVariant;
  }>(),
  {
    class: undefined,
    size: "default",
    type: "button",
    variant: "default"
  }
);

const attrs = useAttrs();
const delegatedAttrs = computed(() => {
  const { class: _class, ...rest } = attrs;
  return rest;
});
</script>

<template>
  <button
    v-bind="delegatedAttrs"
    :type="type"
    :class="cn(buttonVariants({ variant, size }), props.class)"
  >
    <slot />
  </button>
</template>
