import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { libraryApi, previewApi, type LibrarySong, type PreviewInfo } from '@/api'

/**
 * 全局播放器 store。
 *
 * 单例 HTMLAudioElement，由 store 管理 src / play / pause；
 * 视图（底部播放条）观察 store 的状态自动更新。
 */
export interface NowPlaying {
  source: 'remote' | 'local'
  /** remote 时：'netease' | 'qq'；local 时：'library' */
  platform: string
  id: string
  name: string
  artist: string
  album?: string | null
  cover_url?: string | null
  duration_ms?: number
  url: string
  audio_format?: string
  bitrate?: number
}

export const usePlayerStore = defineStore('player', () => {
  // 整个 app 共用一个 audio 元素
  const audio = new Audio()
  audio.preload = 'metadata'
  audio.crossOrigin = 'anonymous'

  const current = ref<NowPlaying | null>(null)
  const playing = ref(false)
  const loading = ref(false)
  const positionSec = ref(0)
  const durationSec = ref(0)
  const volume = ref(0.8)
  audio.volume = volume.value

  audio.addEventListener('timeupdate', () => {
    positionSec.value = audio.currentTime
  })
  audio.addEventListener('durationchange', () => {
    if (!isNaN(audio.duration)) durationSec.value = audio.duration
  })
  audio.addEventListener('play', () => {
    playing.value = true
  })
  audio.addEventListener('pause', () => {
    playing.value = false
  })
  audio.addEventListener('waiting', () => {
    loading.value = true
  })
  audio.addEventListener('canplay', () => {
    loading.value = false
  })
  audio.addEventListener('ended', () => {
    playing.value = false
    positionSec.value = 0
  })
  audio.addEventListener('error', () => {
    loading.value = false
    playing.value = false
  })

  const positionPct = computed(() =>
    durationSec.value > 0 ? (positionSec.value / durationSec.value) * 100 : 0,
  )

  /** 播放远端在线试听（网易云 / QQ）。 */
  const playRemote = async (platform: 'netease' | 'qq', id: string) => {
    loading.value = true
    try {
      const info: PreviewInfo = await previewApi.song(platform, id, 'standard')
      current.value = {
        source: 'remote',
        platform,
        id,
        name: info.name,
        artist: info.primary_artist,
        album: info.album,
        cover_url: info.cover_url,
        duration_ms: info.duration_ms,
        url: info.url,
        audio_format: info.audio_format,
        bitrate: info.bitrate,
      }
      audio.src = info.url
      await audio.play()
    } finally {
      loading.value = false
    }
  }

  /** 播放本地库的歌（流式）。 */
  const playLocal = (song: LibrarySong) => {
    current.value = {
      source: 'local',
      platform: 'library',
      id: String(song.id),
      name: song.name,
      artist: song.artist,
      album: song.album,
      cover_url: null,
      duration_ms: song.duration_ms,
      url: libraryApi.streamUrl(song.id),
      audio_format: song.audio_format ?? undefined,
      bitrate: song.bitrate ?? undefined,
    }
    audio.src = current.value.url
    audio.play()
  }

  const togglePlay = () => {
    if (!current.value) return
    if (audio.paused) audio.play()
    else audio.pause()
  }

  const seek = (sec: number) => {
    if (durationSec.value > 0) {
      audio.currentTime = Math.max(0, Math.min(durationSec.value, sec))
    }
  }

  const setVolume = (v: number) => {
    volume.value = v
    audio.volume = v
  }

  const stop = () => {
    audio.pause()
    audio.removeAttribute('src')
    audio.load()
    current.value = null
    playing.value = false
    positionSec.value = 0
    durationSec.value = 0
  }

  return {
    current,
    playing,
    loading,
    positionSec,
    durationSec,
    positionPct,
    volume,
    playRemote,
    playLocal,
    togglePlay,
    seek,
    setVolume,
    stop,
  }
})
