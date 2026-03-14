<script setup lang="ts">
import { CalendarCheck2, Clock3, PhoneCall } from "lucide-vue-next";

import { Button } from "@/components/ui/button";

const highlights = [
  {
    title: "Same-day scheduling",
    description: "Fast triage for urgent pain, chipped teeth, and swelling.",
    icon: CalendarCheck2
  },
  {
    title: "Predictable appointment flow",
    description: "Clear intake, reminders, and follow-up windows for every visit.",
    icon: Clock3
  },
  {
    title: "Direct patient contact",
    description: "Phone-first support for confirmations, changes, and quick questions.",
    icon: PhoneCall
  }
];
</script>

<template>
  <section class="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
    <div class="space-y-6">
      <div class="inline-flex items-center rounded-full border border-border/80 bg-background/90 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
        Astro + Vue + shadcn-vue
      </div>

      <div class="space-y-4">
        <h1 class="max-w-3xl text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          Dental clinic frontend, scaffolded cleanly and ready for real features.
        </h1>
        <p class="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
          This app uses Astro for the shell, Vue 3 for interactive islands, Tailwind CSS v4, and
          shadcn-vue conventions for UI components.
        </p>
      </div>

      <div class="flex flex-wrap gap-3">
        <Button>Book consultation</Button>
        <Button variant="outline">Open patient portal</Button>
      </div>
    </div>

    <div class="rounded-[28px] border border-border/70 bg-card/80 p-5 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
      <div class="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
        <article
          v-for="item in highlights"
          :key="item.title"
          class="rounded-2xl border border-border/70 bg-background/80 p-5"
        >
          <component :is="item.icon" class="mb-4 size-5 text-primary" />
          <h2 class="text-base font-semibold text-foreground">
            {{ item.title }}
          </h2>
          <p class="mt-2 text-sm leading-6 text-muted-foreground">
            {{ item.description }}
          </p>
        </article>
      </div>
    </div>
  </section>
</template>
