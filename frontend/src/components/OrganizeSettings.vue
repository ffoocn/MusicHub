<template>
  <div class="space-y-6">
    <MusicCard title="目录布局" description="修改后自动保存，下一首下载即按新规则保存。">
      <div v-if="loading" class="py-10 text-center text-theme-sm text-gray-500 dark:text-gray-400">
        加载中...
      </div>
      <div v-else class="space-y-4">
        <OptionCard
          v-model="form['organize.dir_layout']"
          value="artist-song"
          title="简化"
          description="<歌手>/<歌曲>.flac"
          @change="autoSave"
        />
        <OptionCard
          v-model="form['organize.dir_layout']"
          value="artist-album-song"
          title="完整"
          description="<歌手>/<专辑>/<歌曲>.flac（推荐）"
          @change="autoSave"
        />
      </div>
    </MusicCard>

    <MusicCard title="文件命名">
      <div class="space-y-4">
        <OptionCard
          v-model="form['organize.filename_format']"
          value="name"
          title="仅歌名"
          description="七里香.flac"
          @change="autoSave"
        />
        <OptionCard
          v-model="form['organize.filename_format']"
          value="name-artist"
          title="歌名 + 歌手"
          description="七里香 - 周杰伦.flac"
          @change="autoSave"
        />
        <OptionCard
          v-model="form['organize.filename_format']"
          value="name-artist-album"
          title="歌名 + 歌手 + 专辑"
          description="七里香 - 周杰伦 - 七里香.flac"
          @change="autoSave"
        />
      </div>
    </MusicCard>

    <MusicCard title="m3u8 文件名与路径">
      <div class="space-y-5">
        <label class="block">
          <span class="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">文件名模板</span>
          <input
            v-model="form['m3u.filename_template']"
            type="text"
            placeholder="[{platform}] {name}"
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
            @blur="autoSave"
          />
        </label>
        <div class="flex flex-wrap gap-2">
          <MusicButton variant="outline" size="xs" @click="applyM3uPreset('[{platform}] {name}')">
            [平台] 歌单名
          </MusicButton>
          <MusicButton variant="outline" size="xs" @click="applyM3uPreset('{name}')">
            仅歌单名
          </MusicButton>
          <MusicButton variant="outline" size="xs" @click="applyM3uPreset('{platform} - {name}')">
            平台 - 歌单名
          </MusicButton>
        </div>
        <p class="text-theme-sm text-gray-500 dark:text-gray-400">
          可用变量：<code>{platform}</code> 平台标识（netease/qq）、<code>{name}</code> 歌单名。修改后下次同步歌单时生效。
        </p>

        <label class="block">
          <span class="mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300">路径前缀</span>
          <input
            v-model="form['m3u.path_root']"
            type="text"
            placeholder="留空写真实绝对路径，例如填 /music"
            class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
            @blur="autoSave"
          />
        </label>
        <p class="text-theme-sm text-gray-500 dark:text-gray-400">
          歌曲会按 <code>MUSIC_DIR</code> 下载到本机磁盘，m3u8 里的歌曲行会用这个前缀替换实际目录。已下载歌曲不会自动改名，可以删除后重新下载或手动整理。
        </p>
      </div>
    </MusicCard>
  </div>
</template>

<script setup lang="ts">
import { defineComponent, h, onMounted, reactive, ref } from 'vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicCard from '@/components/music/MusicCard.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import { settingsApi } from '@/api'

const OptionCard = defineComponent({
  props: {
    modelValue: { type: String, required: true },
    value: { type: String, required: true },
    title: { type: String, required: true },
    description: { type: String, required: true },
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          class: [
            'flex w-full items-start gap-3 rounded-xl border p-4 text-left transition',
            props.modelValue === props.value
              ? 'border-brand-300 bg-brand-50 dark:border-brand-500/30 dark:bg-brand-500/10'
              : 'border-gray-200 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/[0.03]',
          ],
          onClick: () => {
            emit('update:modelValue', props.value)
            emit('change')
          },
        },
        [
          h('span', {
            class: [
              'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border',
              props.modelValue === props.value
                ? 'border-brand-500 bg-brand-500'
                : 'border-gray-300 dark:border-gray-700',
            ],
          }, props.modelValue === props.value ? [h('span', { class: 'size-2 rounded-full bg-white' })] : []),
          h('span', [
            h('span', { class: 'block text-theme-sm font-semibold text-gray-800 dark:text-white/90' }, props.title),
            h('span', { class: 'mt-1 block text-theme-sm text-gray-500 dark:text-gray-400' }, props.description),
          ]),
        ],
      )
  },
})

const loading = ref(true)
const form = reactive<Record<string, any>>({})
const message = useMusicToast()

let saveTimer: number | null = null

const autoSave = () => {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = window.setTimeout(async () => {
    try {
      await settingsApi.update({
        'organize.dir_layout': form['organize.dir_layout'],
        'organize.filename_format': form['organize.filename_format'],
        'm3u.filename_template': form['m3u.filename_template'] ?? '[{platform}] {name}',
        'm3u.path_root': form['m3u.path_root'] ?? '',
      })
      message.success('已保存', 1200)
    } catch (e: any) {
      message.error(`保存失败：${e?.message ?? e}`)
    }
  }, 400)
}

const applyM3uPreset = (tpl: string) => {
  form['m3u.filename_template'] = tpl
  autoSave()
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
