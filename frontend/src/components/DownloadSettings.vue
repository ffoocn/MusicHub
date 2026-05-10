<template>
  <MusicCard title="下载偏好" description="修改后会自动保存，下一首下载即生效。">
    <div v-if="loading" class="py-10 text-center text-theme-sm text-gray-500 dark:text-gray-400">
      加载中...
    </div>
    <div v-else class="grid gap-6 lg:grid-cols-2">
      <section class="space-y-4">
        <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">下载</h3>
        <FormField label="最高音质">
          <select
            v-model="form['download.max_quality']"
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-theme-sm text-gray-700 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            @change="autoSave"
          >
            <option v-for="opt in qualityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </FormField>
        <FormField label="并发数">
          <input
            v-model.number="form['download.concurrency']"
            type="number"
            min="1"
            max="10"
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            @change="autoSave"
          />
        </FormField>
        <FormField label="单首重试次数">
          <input
            v-model.number="form['download.retry_times']"
            type="number"
            min="0"
            max="10"
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            @change="autoSave"
          />
        </FormField>
      </section>

      <section class="space-y-3">
        <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">元数据</h3>
        <SettingSwitch v-model="form['meta.embed_cover']" label="嵌入封面" @change="autoSave" />
        <SettingSwitch v-model="form['meta.embed_lyric']" label="嵌入歌词" @change="autoSave" />
        <SettingSwitch v-model="form['meta.save_lrc_sidecar']" label="旁存 .lrc 文件" @change="autoSave" />
        <SettingSwitch v-model="form['meta.save_jpg_sidecar']" label="旁存 .jpg 封面" @change="autoSave" />
        <SettingSwitch v-model="form['meta.write_id3_tags']" label="写 ID3 / FLAC 标签" @change="autoSave" />
      </section>
    </div>
  </MusicCard>
</template>

<script setup lang="ts">
import { defineComponent, h, onMounted, reactive, ref } from 'vue'
import MusicCard from '@/components/music/MusicCard.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import { settingsApi } from '@/api'

const FormField = defineComponent({
  props: { label: { type: String, required: true } },
  setup(props, { slots }) {
    return () =>
      h('label', { class: 'block' }, [
        h('span', { class: 'mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300' }, props.label),
        slots.default?.(),
      ])
  },
})

const SettingSwitch = defineComponent({
  props: {
    modelValue: { type: Boolean, required: true },
    label: { type: String, required: true },
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          class:
            'flex w-full items-center justify-between rounded-xl border border-gray-200 px-4 py-3 text-left text-theme-sm font-medium text-gray-800 transition hover:bg-gray-50 dark:border-gray-800 dark:text-white/90 dark:hover:bg-white/[0.03]',
          onClick: () => {
            emit('update:modelValue', !props.modelValue)
            emit('change')
          },
        },
        [
          props.label,
          h(
            'span',
            {
              class: [
                'relative inline-flex h-6 w-11 items-center rounded-full transition',
                props.modelValue ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-700',
              ],
            },
            [
              h('span', {
                class: [
                  'inline-block size-5 rounded-full bg-white shadow-theme-xs transition',
                  props.modelValue ? 'translate-x-5' : 'translate-x-0.5',
                ],
              }),
            ],
          ),
        ],
      )
  },
})

const loading = ref(true)
const form = reactive<Record<string, any>>({})
const message = useMusicToast()

const qualityOptions = [
  { label: '无损（FLAC）', value: 'lossless' },
  { label: '极高（320k MP3 / 640k OGG）', value: 'exhigh' },
  { label: '标准（128k MP3）', value: 'standard' },
]

let saveTimer: number | null = null

const autoSave = () => {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = window.setTimeout(async () => {
    try {
      await settingsApi.update({
        'download.max_quality': form['download.max_quality'],
        'download.concurrency': form['download.concurrency'],
        'download.retry_times': form['download.retry_times'],
        'meta.embed_cover': form['meta.embed_cover'],
        'meta.embed_lyric': form['meta.embed_lyric'],
        'meta.save_lrc_sidecar': form['meta.save_lrc_sidecar'],
        'meta.save_jpg_sidecar': form['meta.save_jpg_sidecar'],
        'meta.write_id3_tags': form['meta.write_id3_tags'],
      })
      message.success('已保存', 1200)
    } catch (e: any) {
      message.error(`保存失败：${e?.message ?? e}`)
    }
  }, 400)
}

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    Object.assign(form, data)
  } catch (e: any) {
    message.error(`加载失败：${e?.message ?? e}`)
  } finally {
    loading.value = false
  }
})
</script>
