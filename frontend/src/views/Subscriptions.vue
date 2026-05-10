<template>
  <div class="space-y-6">
    <!-- 顶部动作按钮组（hero 标题已移除，页名由顶栏 document.title 体现） -->
    <div class="flex flex-wrap items-center justify-end gap-2">
      <MusicButton variant="outline" :loading="loading" @click="refresh">
        <RefreshCw class="size-4" />
        刷新
      </MusicButton>
      <MusicButton variant="outline" :loading="syncingAll" @click="syncAll">
        <RotateCcw class="size-4" />
        全部同步
      </MusicButton>
      <MusicButton variant="outline" :loading="regening" @click="regenAll">
        <ListMusic class="size-4" />
        重建 m3u
      </MusicButton>
      <MusicButton @click="showAdd = true">
        <Plus class="size-4" />
        添加订阅
      </MusicButton>
    </div>

    <!-- ============== Main Grid：左侧明细/趋势 + 右侧构成/活动 ============== -->
    <div class="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <div class="space-y-6 xl:col-span-2">
      <div class="flex h-[700px] flex-col rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">订阅明细</h3>
            <p class="mt-0.5 text-theme-xs text-gray-500 dark:text-gray-400">
              {{ filteredItems.length }} / {{ items.length }} 条
              <span v-if="autoAddedCount && !hideAutoAdded">· 含 {{ autoAddedCount }} 自动添加</span>
            </p>
          </div>
          <div class="grid w-full gap-2 sm:w-auto sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-center">
            <div class="relative">
              <Search class="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
              <input
                v-model="search"
                type="search"
                placeholder="搜索订阅名 / 创建者..."
                class="h-9 w-full rounded-lg border border-gray-200 bg-white pl-9 pr-3 text-theme-sm text-gray-700 placeholder-gray-400 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:placeholder-gray-500 lg:w-56"
              />
            </div>
            <select
              v-model="filterPlatform"
              class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-theme-sm text-gray-700 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
            >
              <option v-for="opt in platformOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select
              v-model="filterKind"
              class="h-9 rounded-lg border border-gray-200 bg-white px-3 text-theme-sm text-gray-700 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
            >
              <option v-for="opt in kindOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <label class="inline-flex h-9 items-center gap-2 rounded-lg border border-gray-200 px-3 text-theme-xs text-gray-600 dark:border-gray-700 dark:text-gray-400">
              <input
                v-model="hideAutoAdded"
                type="checkbox"
                class="size-3.5 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-600 dark:bg-gray-900"
              />
              隐藏自动
            </label>
          </div>
        </div>

        <!--
          订阅明细滚动容器：
          · max-h-[560px] 限定区域最大高度，超过后启用纵向滚动；
          · overflow-auto 同时支持横/纵向滚动（窄屏时横向不再被剥夺）；
          · thead 用 sticky top-0 + 半透明背景，保证滚动时表头始终可见。
        -->
        <div class="min-h-0 flex-1 overflow-auto">
          <table class="w-full table-fixed">
            <colgroup>
              <col class="w-auto" />
              <col style="width: 132px" />
              <col style="width: 148px" />
              <col style="width: 96px" />
              <col style="width: 64px" />
              <col style="width: 96px" />
            </colgroup>
            <thead class="sticky top-0 z-10 bg-white/95 backdrop-blur-sm dark:bg-gray-900/90">
              <tr class="whitespace-nowrap text-left text-theme-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
                <th class="border-b border-gray-200 px-5 py-3 dark:border-gray-800 sm:px-6">订阅</th>
                <th class="border-b border-gray-200 px-3 py-3 dark:border-gray-800">类型/平台</th>
                <th class="border-b border-gray-200 px-3 py-3 dark:border-gray-800">上次同步</th>
                <th class="border-b border-gray-200 px-3 py-3 dark:border-gray-800">间隔</th>
                <th class="border-b border-gray-200 px-3 py-3 dark:border-gray-800">启用</th>
                <th class="border-b border-gray-200 px-3 py-3 pr-5 text-right dark:border-gray-800 sm:pr-6">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-if="loading && !items.length">
                <td colspan="6" class="px-5 py-10 text-center text-theme-sm text-gray-500 dark:text-gray-400">加载中...</td>
              </tr>
              <tr v-else-if="!filteredItems.length">
                <td colspan="6" class="px-5 py-10 text-center text-theme-sm text-gray-500 dark:text-gray-400">
                  <template v-if="hideAutoAdded && items.some((s) => s.auto_added)">
                    没有匹配的订阅 · 已隐藏 {{ autoAddedCount }} 个 meta 自动添加项
                    <button type="button" class="ml-2 font-medium text-brand-500 hover:text-brand-600" @click="hideAutoAdded = false">
                      显示
                    </button>
                  </template>
                  <template v-else>没有匹配的订阅</template>
                </td>
              </tr>
              <tr
                v-for="row in pagedItems"
                v-else
                :key="row.id"
                :class="[
                  'transition hover:bg-gray-50 dark:hover:bg-white/[0.02]',
                  row.last_error ? 'bg-error-50/40 dark:bg-error-500/5' : '',
                  row.auto_added ? 'bg-gray-50/60 dark:bg-white/[0.015]' : '',
                  isRowClickable(row) ? 'cursor-pointer' : '',
                ]"
                @click="onRowClick(row)"
              >
                <!-- 订阅：封面 + 名称 + 创建者 + 次级徽章（自动/聚合/无 m3u） -->
                <td class="px-5 py-3 sm:px-6">
                  <div class="flex min-w-0 items-start gap-3">
                    <div class="size-10 shrink-0 overflow-hidden rounded-lg bg-gray-100 dark:bg-white/5">
                      <img v-if="row.cover_url" :src="row.cover_url" :alt="row.name" class="size-full object-cover" loading="lazy" />
                      <div v-else class="flex size-full items-center justify-center text-gray-500 dark:text-gray-400">
                        <component :is="rowFallbackIcon(row)" class="size-4" />
                      </div>
                    </div>
                    <div class="min-w-0 flex-1">
                      <p
                        :class="[
                          'truncate text-theme-sm font-medium',
                          row.enabled ? 'text-gray-800 dark:text-white/90' : 'text-gray-400 line-through dark:text-gray-500',
                          row.last_error ? 'text-error-600 dark:text-error-500' : '',
                        ]"
                        :title="row.name"
                      >{{ row.name }}</p>
                      <p class="mt-0.5 truncate text-theme-xs text-gray-500 dark:text-gray-400" :title="row.creator || ''">
                        {{ row.creator || '无创建者' }}
                      </p>
                      <div
                        v-if="row.auto_added || row.cross_platform || !row.generate_m3u || row.last_error"
                        class="mt-1 flex flex-wrap items-center gap-1"
                      >
                        <MusicBadge v-if="row.auto_added" color="warning" size="sm">
                          {{ row.parent_subscription_id ? '子订阅' : '自动 · 未归属' }}
                        </MusicBadge>
                        <MusicBadge v-if="row.cross_platform" color="brand" size="sm">聚合</MusicBadge>
                        <MusicBadge v-if="!row.generate_m3u" color="gray" size="sm">无 m3u</MusicBadge>
                        <MusicBadge v-if="row.last_error" color="error" size="sm" :title="row.last_error">异常</MusicBadge>
                      </div>
                    </div>
                  </div>
                </td>

                <!-- 类型 / 平台：单行不换行 -->
                <td class="px-3 py-3 align-middle">
                  <div class="flex items-center gap-2 whitespace-nowrap">
                    <MusicBadge :color="targetTypeColor(row.target_type)" size="sm">{{ targetTypeLabel(row.target_type) }}</MusicBadge>
                    <MusicPlatformIcon :platform="row.platform" size="xs" />
                  </div>
                </td>

                <!-- 上次同步：单行不换行 -->
                <td
                  class="px-3 py-3 align-middle text-theme-sm text-gray-600 dark:text-gray-300"
                  :title="row.last_sync_at ? formatDt(row.last_sync_at) : '从未同步'"
                >
                  <div class="flex items-center gap-1.5 whitespace-nowrap">
                    <span>{{ row.last_sync_at ? relativeTime(row.last_sync_at) : '从未' }}</span>
                    <MusicBadge v-if="row.last_sync_new_count > 0" color="success" size="sm">+{{ row.last_sync_new_count }}</MusicBadge>
                  </div>
                </td>

                <!-- 间隔 -->
                <td class="px-3 py-3 align-middle" @click.stop>
                  <div class="flex items-center gap-1 whitespace-nowrap">
                    <input
                      type="number"
                      :value="row.sync_interval_hours"
                      min="1"
                      max="240"
                      class="h-8 w-14 rounded-lg border border-gray-200 bg-white px-2 text-right text-theme-sm text-gray-800 focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                      @change="(e) => updateInterval(row, Number((e.target as HTMLInputElement).value))"
                    />
                    <span class="text-theme-xs text-gray-500 dark:text-gray-400">h</span>
                  </div>
                </td>

                <!--
                  启用开关
                  · @click.stop 阻止冒泡到 <tr> 的整行点击（避免点开关时跳详情）；
                  · relative z-[1] 让按钮始终在 hover 半透明 overlay 之上，确保事件能命中；
                  · enabledBusy[row.id] 提供加载态，避免多次点击造成竞态。
                -->
                <td class="px-3 py-3 align-middle" @click.stop>
                  <button
                    type="button"
                    :disabled="enabledBusy[row.id]"
                    :class="[
                      'relative z-[1] inline-flex h-6 w-11 cursor-pointer items-center rounded-full transition',
                      row.enabled ? 'bg-brand-500' : 'bg-gray-200 dark:bg-gray-700',
                      enabledBusy[row.id] ? 'opacity-60 cursor-wait' : '',
                    ]"
                    :title="row.enabled ? '点击停用' : '点击启用'"
                    @click.stop="toggleEnabled(row, !row.enabled)"
                  >
                    <span
                      :class="[
                        'inline-block size-5 rounded-full bg-white shadow-theme-xs transition',
                        row.enabled ? 'translate-x-5' : 'translate-x-0.5',
                      ]"
                    />
                  </button>
                </td>

                <!-- 操作 -->
                <td class="px-3 py-3 pr-5 align-middle sm:pr-6" @click.stop>
                  <div class="flex items-center justify-end gap-1 whitespace-nowrap">
                    <button
                      type="button"
                      class="inline-flex size-8 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-100 hover:text-brand-500 dark:text-gray-400 dark:hover:bg-white/5"
                      title="立即同步"
                      @click="onSyncOne(row.id)"
                    >
                      <RotateCcw class="size-4" />
                    </button>
                    <button
                      type="button"
                      class="inline-flex size-8 items-center justify-center rounded-lg text-gray-500 transition hover:bg-error-50 hover:text-error-600 dark:text-gray-400 dark:hover:bg-error-500/10 dark:hover:text-error-500"
                      title="删除"
                      @click="removeOne(row)"
                    >
                      <Trash2 class="size-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="filteredItems.length > pageSize" class="flex flex-col gap-3 border-t border-gray-200 px-5 py-3 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p class="text-theme-xs text-gray-500 dark:text-gray-400">
            第 {{ page }} / {{ pageCount }} 页，共 {{ filteredItems.length }} 条
          </p>
          <div class="flex items-center gap-2">
            <MusicButton variant="outline" size="xs" :disabled="page <= 1" @click="page -= 1">上一页</MusicButton>
            <MusicButton variant="outline" size="xs" :disabled="page >= pageCount" @click="page += 1">下一页</MusicButton>
          </div>
        </div>
      </div>

      <!-- 同步活跃度 -->
      <div class="flex h-[300px] flex-col rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex flex-col gap-3 px-5 pt-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">同步活跃度</h3>
            <p class="mt-1 text-theme-sm text-gray-500 dark:text-gray-400">
              {{ activityRangeLabel }} 同步带来的新增歌曲分布
            </p>
          </div>
          <div class="inline-flex rounded-lg bg-gray-100 p-0.5 dark:bg-gray-800">
            <button
              v-for="tab in activityTabs"
              :key="tab.key"
              :class="[
                'rounded-md px-3 py-1.5 text-theme-xs font-medium transition',
                activityTab === tab.key
                  ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-700 dark:text-white'
                  : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white',
              ]"
              @click="activityTab = tab.key"
            >{{ tab.label }}</button>
          </div>
        </div>
        <div class="min-h-0 flex-1 px-2 pb-4 pt-3 sm:px-4">
          <div v-if="activityChart.points.length" class="relative">
            <svg viewBox="0 0 600 190" preserveAspectRatio="none" class="h-[145px] w-full">
              <defs>
                <linearGradient id="subActivityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#465fff" stop-opacity="0.32" />
                  <stop offset="100%" stop-color="#465fff" stop-opacity="0" />
                </linearGradient>
              </defs>
              <line
                v-for="line in activityGridLines"
                :key="`agl-${line.y}`"
                x1="0"
                x2="600"
                :y1="line.y"
                :y2="line.y"
                stroke="currentColor"
                class="text-gray-200 dark:text-gray-800"
                stroke-width="1"
                stroke-dasharray="4 4"
              />
              <path :d="activityChart.area" fill="url(#subActivityGrad)" />
              <path
                :d="activityChart.line"
                fill="none"
                stroke="#465fff"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <circle
                v-for="(pt, idx) in activityChart.points"
                :key="`apt-${idx}`"
                :cx="pt.x"
                :cy="pt.y"
                r="3.5"
                fill="#fff"
                stroke="#465fff"
                stroke-width="2"
              />
            </svg>
            <div class="mt-2 flex items-center justify-between gap-2 px-2 text-theme-xs text-gray-400 dark:text-gray-500">
              <span v-for="(label, idx) in activityXLabels" :key="`alx-${idx}`" class="truncate">{{ label }}</span>
            </div>
          </div>
          <div v-else class="px-3 py-10 text-center text-theme-sm text-gray-400 dark:text-gray-500">
            {{ activityRangeLabel }}内还没有同步事件。
          </div>
        </div>
      </div>
      </div>

      <div class="space-y-6">
      <!-- 来源构成（平台 + 类型 进度条） -->
      <div class="flex h-[540px] flex-col rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-center justify-between gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:px-6">
          <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">来源构成</h3>
          <span class="text-theme-xs text-gray-500 dark:text-gray-400">{{ items.length }} 条</span>
        </div>
        <div class="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
          <div>
            <p class="text-theme-xs font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">按平台</p>
            <div class="mt-3 space-y-3">
              <div v-for="row in platformBreakdown" :key="`pb-${row.key}`" class="space-y-1.5">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex min-w-0 items-center gap-2">
                    <MusicPlatformIcon :platform="row.key" size="sm" />
                    <span class="truncate text-theme-sm font-medium text-gray-700 dark:text-gray-300">{{ row.label }}</span>
                  </div>
                  <span class="text-theme-xs text-gray-500 dark:text-gray-400">{{ row.value }} · {{ row.pct }}%</span>
                </div>
                <MusicProgressBar :value="row.pct" />
              </div>
            </div>
          </div>
          <div class="border-t border-gray-100 pt-5 dark:border-gray-800">
            <p class="text-theme-xs font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">按类型</p>
            <div class="mt-3 space-y-3">
              <div v-for="row in typeBreakdown" :key="`tb-${row.key}`" class="space-y-1.5">
                <div class="flex items-center justify-between gap-2">
                  <div class="flex min-w-0 items-center gap-2">
                    <span :class="['flex size-6 shrink-0 items-center justify-center rounded-md', row.toneClass]">
                      <component :is="row.icon" class="size-3.5" />
                    </span>
                    <span class="truncate text-theme-sm font-medium text-gray-700 dark:text-gray-300">{{ row.label }}</span>
                  </div>
                  <span class="text-theme-xs text-gray-500 dark:text-gray-400">{{ row.value }} · {{ row.pct }}%</span>
                </div>
                <MusicProgressBar :value="row.pct" :color="row.color" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 同步活动时间线（SaaS Activities） -->
      <div class="flex h-[460px] flex-col rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-center justify-between gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:px-6">
          <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">同步活动</h3>
          <span class="text-theme-xs text-gray-500 dark:text-gray-400">最近 6 条</span>
        </div>
        <div v-if="activities.length" class="min-h-0 flex-1 px-5 py-2 sm:px-6">
          <div
            v-for="event in activities"
            :key="`act-${event.id}`"
            class="flex items-start gap-3 border-b border-gray-100 py-3 last:border-0 dark:border-gray-800"
          >
            <span :class="['flex size-9 shrink-0 items-center justify-center rounded-full', event.bg]">
              <component :is="event.icon" :class="['size-4', event.color]" />
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90" :title="event.name">{{ event.name }}</p>
              <p class="mt-0.5 truncate text-theme-xs text-gray-500 dark:text-gray-400">{{ event.detail }}</p>
            </div>
            <span class="shrink-0 text-theme-xs text-gray-400 dark:text-gray-500" :title="event.dateTitle">{{ event.timeLabel }}</span>
          </div>
        </div>
        <div v-else class="px-5 py-10 text-center text-theme-sm text-gray-400 dark:text-gray-500 sm:px-6">
          还没有同步活动。
        </div>
      </div>
      </div>
    </div>

    <!-- ============== 添加订阅 Modal：快速订阅 + 搜索/ID 自定义 ============== -->
    <MusicModal
      :open="showAdd"
      title="添加订阅"
      size="xl"
      @close="showAdd = false"
    >
      <div class="space-y-4">
        <!-- 全局配置：三种订阅共用一套 同步间隔 / 立即启用 / 生成 m3u8 -->
        <div class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-gray-200 px-4 py-3 dark:border-gray-800">
          <label class="inline-flex items-center gap-2 text-theme-sm font-medium text-gray-800 dark:text-white/90">
            同步间隔
            <input
              v-model.number="globalCfg.sync_interval_hours"
              type="number"
              min="1"
              max="240"
              class="h-9 w-20 rounded-lg border border-gray-300 bg-white px-2 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            />
            <span class="text-theme-xs text-gray-500 dark:text-gray-400">小时</span>
          </label>
          <SwitchField v-model="globalCfg.enabled" label="立即启用" />
          <SwitchField
            v-model="globalCfg.generate_m3u"
            label="生成 m3u8"
            description="关闭后只下载歌曲，不在 _m3u 目录生成播放列表。"
          />
        </div>

        <!-- 1. 动态热门歌单（受控折叠：与下方两块一次只能展开一个） -->
        <details
          :open="accordion === 'hot'"
          class="group rounded-xl border border-gray-200 dark:border-gray-800"
        >
          <summary
            class="flex cursor-pointer select-none items-center justify-between gap-3 px-4 py-3"
            @click.prevent="toggleAcc('hot')"
          >
            <span class="flex items-center gap-2 text-theme-sm font-semibold text-gray-800 dark:text-white/90">
              动态热门歌单
              <span
                v-if="hotCat.categories.length"
                class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-theme-xs font-normal text-gray-600 dark:bg-white/10 dark:text-gray-300"
              >已选 {{ hotCat.categories.length }} 个分类</span>
            </span>
            <svg class="size-4 shrink-0 text-gray-500 transition-transform group-open:rotate-180" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>
          </summary>
          <div class="border-t border-gray-100 px-4 pb-4 pt-3 dark:border-gray-800">
            <div class="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
              <Field label="平台">
                <select
                  v-model="hotCat.platform"
                  class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                >
                  <option value="netease">网易云音乐</option>
                  <option value="qq">QQ 音乐</option>
                </select>
              </Field>
              <Field label="选取方式">
                <select
                  v-model="hotCat.pick_mode"
                  class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                >
                  <option value="top_play_count">播放量排名靠前</option>
                  <option value="random">随机</option>
                </select>
              </Field>
              <Field label="每类取前 N 个">
                <input
                  v-model.number="hotCat.top_n"
                  type="number"
                  min="1"
                  max="30"
                  class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </Field>
              <Field label="候选池/页">
                <input
                  v-model.number="hotCat.pool_size"
                  type="number"
                  min="1"
                  max="100"
                  class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </Field>
              <Field label="掉榜处理">
                <select
                  v-model="hotCat.drop_policy"
                  class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                >
                  <option value="keep_history">保留历史入选</option>
                  <option value="strict">严格保持 TopN</option>
                </select>
              </Field>
            </div>
            <p class="mt-2 text-theme-xs leading-relaxed text-gray-500 dark:text-gray-400">
              选择多个分类时会为每个分类分别创建一个动态热门订阅；“保留历史入选”表示歌单掉出 TopN 后仍继续订阅。
            </p>
            <div class="mt-3">
              <div class="rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-white/[0.03]">
                <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p class="text-theme-xs font-medium text-gray-700 dark:text-gray-300">广场分类（可多选）</p>
                    <p class="mt-0.5 text-theme-xs text-gray-500 dark:text-gray-400">
                      共 {{ hotCatCategoryOptions.length }} 个分类，已选 {{ hotCat.categories.length }} 个
                    </p>
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <button
                      v-if="hasUnselectedHotCategories"
                      type="button"
                      class="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-theme-xs font-medium text-brand-700 hover:bg-brand-100 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-300"
                      @click="selectAllHotCategories"
                    >全选</button>
                    <button
                      v-if="hotCat.categories.length"
                      type="button"
                      class="rounded-lg border border-gray-200 bg-white px-3 py-2 text-theme-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-white/5"
                      @click="hotCat.categories = []"
                    >清空所选</button>
                  </div>
                </div>

                <div
                  v-if="hotCat.categories.length >= HOTCAT_BULK_CONFIRM_THRESHOLD"
                  class="mt-3 rounded-lg border border-warning-200 bg-warning-50 px-3 py-2 text-theme-xs leading-relaxed text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-300"
                >
                  已选择 {{ hotCat.categories.length }} 个分类，提交时将创建 {{ hotCat.categories.length }} 个动态热门父订阅；每类 Top{{ normalizedHotTopN }}，预计最多维护 {{ estimatedHotChildCount }} 个热门子歌单。
                </div>

                <p v-if="hotCatCategoriesLoading" class="py-4 text-theme-xs text-gray-500 dark:text-gray-400">正在加载列表…</p>
                <div v-else class="mt-3 max-h-80 overflow-y-auto rounded-xl border border-gray-200 bg-white p-3 shadow-theme-xs dark:border-gray-800 dark:bg-gray-900">
                  <div
                    v-if="hotCatCategoryGroups.length"
                    class="space-y-4"
                  >
                    <section
                      v-for="group in hotCatCategoryGroups"
                      :key="group.name"
                    >
                      <div class="mb-2 flex items-center justify-between gap-3">
                        <p class="text-theme-xs font-semibold text-gray-500 dark:text-gray-400">{{ group.name }}</p>
                        <p class="text-theme-xs text-gray-400">{{ group.items.length }} 个</p>
                      </div>
                      <div class="flex flex-wrap gap-2">
                        <button
                          v-for="opt in group.items"
                          :key="`${hotCat.platform}-${opt}`"
                          type="button"
                          :title="opt"
                          :class="[
                            'rounded-full border px-3 py-1.5 text-theme-xs font-medium transition',
                            hotCat.categories.includes(opt)
                              ? 'border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-300'
                              : 'border-gray-200 bg-white text-gray-700 hover:border-brand-200 hover:bg-brand-50/60 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-500/40 dark:hover:bg-brand-500/10 dark:hover:text-brand-300',
                          ]"
                          @click="toggleHotCategory(opt)"
                        >
                          {{ hotCategoryLabel(opt) }}
                        </button>
                      </div>
                    </section>
                  </div>
                  <p v-else class="px-2 py-3 text-theme-xs text-gray-500 dark:text-gray-400">
                    暂无选项，请稍后重试或切换平台。
                  </p>
                </div>
              </div>
            </div>
          </div>
        </details>

        <!-- 2. 其他一键订阅（点击仅切换选中态，最终由底部「添加」一次性提交） -->
        <details
          :open="accordion === 'quick'"
          class="group rounded-xl border border-gray-200 dark:border-gray-800"
        >
          <summary
            class="flex cursor-pointer select-none items-center justify-between gap-3 px-4 py-3"
            @click.prevent="toggleAcc('quick')"
          >
            <span class="flex items-center gap-2 text-theme-sm font-semibold text-gray-800 dark:text-white/90">
              其他一键订阅
              <span
                v-if="quickPicked.size"
                class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-theme-xs font-normal text-gray-600 dark:bg-white/10 dark:text-gray-300"
              >已选 {{ quickPicked.size }} 项</span>
            </span>
            <svg class="size-4 shrink-0 text-gray-500 transition-transform group-open:rotate-180" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>
          </summary>
          <div class="border-t border-gray-100 px-4 pb-4 pt-3 dark:border-gray-800">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div
                v-for="g in quickGroups"
                :key="`qg-${g.kind}`"
                class="flex flex-col gap-2.5 rounded-xl border border-gray-200 p-3 dark:border-gray-800"
              >
                <div class="flex items-center gap-2">
                  <span class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
                    <component :is="g.icon" class="size-4" />
                  </span>
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-1.5">
                      <span class="truncate text-theme-sm font-semibold text-gray-800 dark:text-white/90">{{ g.label }}</span>
                      <MusicBadge :color="g.tagType === 'success' ? 'success' : 'info'" size="sm">{{ g.tag }}</MusicBadge>
                    </div>
                  </div>
                </div>
                <div class="mt-auto flex flex-col gap-1.5">
                  <button
                    v-for="q in g.items"
                    :key="`qb-${q.kind}-${q.platform}`"
                    type="button"
                    :disabled="existingMap.has(q.existingKey)"
                    :title="existingMap.has(q.existingKey) ? `已订阅 ${q.platformLabel}（请到下方列表管理）` : q.platformLabel"
                    :class="[
                      'inline-flex h-9 items-center gap-2 rounded-lg border px-2.5 text-theme-sm font-medium transition',
                      existingMap.has(q.existingKey)
                        ? 'cursor-not-allowed border-success-200 bg-success-50 text-success-700 dark:border-success-500/20 dark:bg-success-500/10 dark:text-success-500'
                        : isQuickPicked(q)
                          ? 'border-brand-300 bg-brand-50 text-brand-700 dark:border-brand-500/40 dark:bg-brand-500/15 dark:text-brand-300'
                          : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-white/5',
                    ]"
                    @click="toggleQuickPick(q)"
                  >
                    <MusicPlatformIcon :platform="q.platform" size="xs" />
                    <span class="truncate">{{ q.platformLabel }}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </details>

        <!-- 3. 自定义添加 —— 同款受控 details -->
        <details
          :open="accordion === 'custom'"
          class="group rounded-xl border border-gray-200 dark:border-gray-800"
        >
          <summary
            class="flex cursor-pointer select-none items-center justify-between gap-3 px-4 py-3"
            @click.prevent="toggleAcc('custom')"
          >
            <span class="flex items-center gap-2 text-theme-sm font-semibold text-gray-800 dark:text-white/90">
              自定义添加
              <span
                v-if="customPickedSummary"
                class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-theme-xs font-normal text-gray-600 dark:bg-white/10 dark:text-gray-300"
              >{{ customPickedSummary }}</span>
            </span>
            <svg class="size-4 shrink-0 text-gray-500 transition-transform group-open:rotate-180" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>
          </summary>
          <div class="space-y-4 border-t border-gray-100 px-4 pb-4 pt-3 dark:border-gray-800">
            <div class="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-white/[0.03]">
              <p class="text-theme-sm font-medium text-gray-800 dark:text-white/90">一次只添加一个自定义订阅</p>
              <p class="mt-1 text-theme-xs text-gray-500 dark:text-gray-400">
                先选择平台和类型，再搜索并确认一个歌单、专辑或歌手；歌手/专辑可额外选择另一平台对应项做聚合。
              </p>
            </div>

            <div class="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <div class="mb-3 flex items-center gap-2">
                <span class="flex size-6 items-center justify-center rounded-full bg-brand-50 text-theme-xs font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">1</span>
                <p class="text-theme-sm font-semibold text-gray-800 dark:text-white/90">选择本次要添加的对象类型</p>
              </div>
              <div class="grid gap-4 sm:grid-cols-[220px_1fr]">
                <Field label="平台">
                  <select
                    v-model="form.platform"
                    class="h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-theme-sm text-gray-800 shadow-theme-xs focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    @change="onPlatformOrTypeChange"
                  >
                    <option value="netease">网易云音乐</option>
                    <option value="qq">QQ 音乐</option>
                  </select>
                </Field>
                <Field label="类型">
                  <SegmentedControl
                    v-model="form.target_type"
                    :items="[
                      { label: '歌单', value: 'playlist' },
                      { label: '专辑', value: 'album' },
                      { label: '歌手', value: 'artist' },
                    ]"
                    @change="onPlatformOrTypeChange"
                  />
                </Field>
              </div>
            </div>

            <div
              :class="[
                'grid gap-4',
                form.target_type === 'artist' || form.target_type === 'album'
                  ? 'xl:grid-cols-2'
                  : 'xl:grid-cols-1',
              ]"
            >
              <div class="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div class="mb-3 flex items-center gap-2">
                  <span class="flex size-6 items-center justify-center rounded-full bg-brand-50 text-theme-xs font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">2</span>
                  <p class="text-theme-sm font-semibold text-gray-800 dark:text-white/90">搜索并确认一个{{ form.target_type === 'artist' ? '歌手' : form.target_type === 'album' ? '专辑' : '歌单' }}</p>
                </div>
                <div
                  v-if="form.id"
                  class="inline-flex max-w-full flex-wrap items-center gap-2 rounded-lg border border-success-200 bg-success-50 px-3 py-2 text-theme-sm text-success-700 dark:border-success-500/20 dark:bg-success-500/10 dark:text-success-500"
                >
                  <span class="min-w-0 truncate">已选 {{ pickedLabel }}</span>
                  <span class="font-mono text-theme-xs opacity-70">id={{ form.id }}</span>
                  <button type="button" class="font-medium text-error-600 dark:text-error-500" @click.stop="clearPrimaryPick">重新选择</button>
                </div>
                <Field v-else :label="searchLabel">
                  <div class="relative">
                    <input
                      v-model="form.searchQuery"
                      type="text"
                      :placeholder="searchPlaceholder"
                      class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
                      @input="onSearchInput"
                      @focus="onSearchFocus"
                    />
                    <SuggestPanel
                      v-if="suggestOpen"
                      :items="suggestItems"
                      :loading="suggestLoading"
                      :empty-label="form.searchQuery ? '没有匹配' : '请输入关键词'"
                      :target-type="form.target_type"
                      :selected-id="form.id"
                      @pick="pickSuggest"
                    />
                  </div>
                  <p
                    v-if="!form.id && customId"
                    class="mt-1 text-theme-xs text-gray-500 dark:text-gray-400"
                  >
                    识别为 ID：<span class="font-mono text-gray-700 dark:text-gray-300">{{ customId }}</span>
                  </p>
                </Field>
              </div>

              <div
                v-if="form.target_type === 'artist' || form.target_type === 'album'"
                class="rounded-xl border border-gray-200 p-4 dark:border-gray-800"
              >
                <div class="mb-3 flex items-center gap-2">
                  <span class="flex size-6 items-center justify-center rounded-full bg-brand-50 text-theme-xs font-semibold text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">3</span>
                  <p class="text-theme-sm font-semibold text-gray-800 dark:text-white/90">可选：补充另一平台对应项</p>
                </div>
                <SwitchField
                  v-model="form.cross_platform"
                  label="全平台聚合"
                  :description="`合并另一平台的同名${form.target_type === 'artist' ? '歌手' : '专辑'}，A 平台缺的歌从 B 补。`"
                />

                <div v-if="form.cross_platform" class="mt-4 space-y-3">
                  <div
                    v-if="form.cross_platform_id"
                    class="inline-flex max-w-full flex-wrap items-center gap-2 rounded-lg border border-success-200 bg-success-50 px-3 py-2 text-theme-sm text-success-700 dark:border-success-500/20 dark:bg-success-500/10 dark:text-success-500"
                  >
                    <span class="min-w-0 truncate">已选 {{ form.crossPickedName }}</span>
                    <span class="font-mono text-theme-xs opacity-70">id={{ form.cross_platform_id }}</span>
                    <button type="button" class="font-medium text-error-600 dark:text-error-500" @click.stop="clearCrossPick">清除</button>
                  </div>
                  <Field v-else :label="`在 ${otherPlatformLabel} 选择对应${form.target_type === 'artist' ? '歌手' : '专辑'}`">
                    <div class="relative">
                      <input
                        v-model="form.crossSearchQuery"
                        type="text"
                        :placeholder="`输入${form.target_type === 'artist' ? '歌手' : '专辑'}名搜索 ${otherPlatformLabel}...`"
                        class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-theme-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
                        @input="onCrossSearchInput"
                        @focus="onCrossSearchFocus"
                      />
                      <SuggestPanel
                        v-if="crossSuggestOpen"
                        :items="crossSuggestItems"
                        :loading="crossSuggestLoading"
                        :empty-label="form.crossSearchQuery ? '没有匹配' : '请输入关键词'"
                        :target-type="form.target_type"
                        :selected-id="form.cross_platform_id"
                        @pick="pickCrossSuggest"
                      />
                    </div>
                  </Field>
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>

      <template #footer>
        <div class="flex justify-end gap-3">
          <MusicButton variant="outline" @click="showAdd = false">取消</MusicButton>
          <MusicButton :loading="adding" @click="submitAll">添加</MusicButton>
        </div>
      </template>
    </MusicModal>

    <MusicConfirmDialog
      :open="Boolean(confirmDelete)"
      title="删除订阅"
      :message="deleteConfirmMessage"
      tone="danger"
      confirmText="删除"
      @close="confirmDelete = null"
      @confirm="confirmRemove"
    >
      <div
        v-if="confirmDelete && childCountOf(confirmDelete)"
        class="mt-4 space-y-2 rounded-xl border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-white/[0.03]"
      >
        <label class="flex cursor-pointer items-start gap-3 text-theme-sm text-gray-700 dark:text-gray-300">
          <input
            v-model="deleteChildAction"
            type="radio"
            value="delete"
            class="mt-0.5 size-4 border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
          />
          <span>
            删除父级和自动子订阅
            <span class="mt-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">默认选项，父级维护的子订阅会一起移除。</span>
          </span>
        </label>
        <label class="flex cursor-pointer items-start gap-3 text-theme-sm text-gray-700 dark:text-gray-300">
          <input
            v-model="deleteChildAction"
            type="radio"
            value="promote"
            class="mt-0.5 size-4 border-gray-300 text-brand-500 focus:ring-brand-500 dark:border-gray-700 dark:bg-gray-900"
          />
          <span>
            保留子订阅为普通订阅
            <span class="mt-0.5 block text-theme-xs text-gray-500 dark:text-gray-400">子订阅会解除父级关系，之后按自己的开关和间隔同步。</span>
          </span>
        </label>
      </div>
    </MusicConfirmDialog>

    <MusicConfirmDialog
      :open="confirmHotBulk"
      title="确认批量创建动态热门订阅"
      :message="hotBulkConfirmMessage"
      tone="warning"
      confirmText="确认创建"
      cancelText="返回调整"
      :loading="adding"
      @close="confirmHotBulk = false"
      @confirm="submitAllConfirmed"
    />
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  defineComponent,
  h,
  onMounted,
  ref,
  watch,
  type Component,
} from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  CheckCircle2,
  Disc3,
  Heart,
  Layers,
  ListMusic,
  Music2,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Sun,
  Trash2,
  Trophy,
  UserRound,
  XCircle,
} from 'lucide-vue-next'
import MusicBadge from '@/components/music/MusicBadge.vue'
import MusicButton from '@/components/music/MusicButton.vue'
import MusicConfirmDialog from '@/components/music/MusicConfirmDialog.vue'
import MusicModal from '@/components/music/MusicModal.vue'
import MusicPlatformIcon from '@/components/music/MusicPlatformIcon.vue'
import MusicProgressBar from '@/components/music/MusicProgressBar.vue'
import { useMusicToast } from '@/components/music/useMusicToast'
import {
  discoverApi,
  subscriptionsApi,
  type QuickSubscribeKind,
  type SubscriptionItem,
  type SuggestItem,
} from '@/api'

interface QuickDef {
  kind: QuickSubscribeKind
  platform: 'netease' | 'qq'
  platformLabel: string
  title: string
  description: string
  existingKey: string
}

interface QuickGroup {
  kind: QuickSubscribeKind
  label: string
  description: string
  tag: string
  tagType: 'success' | 'info'
  icon: Component
  items: QuickDef[]
}

// ===== 内联辅助组件（沿用原有逻辑） =====
const Field = defineComponent({
  props: { label: { type: String, required: true } },
  setup(props, { slots }) {
    return () =>
      h('label', { class: 'block' }, [
        h('span', { class: 'mb-1.5 block text-theme-sm font-medium text-gray-700 dark:text-gray-300' }, props.label),
        slots.default?.(),
      ])
  },
})

/**
 * Toggle switch input —— 完全遵循 TailAdmin 表单元素样式
 * （`https://nextjs-demo.tailadmin.com/form-elements` 中的 Toggle switch input）：
 *
 * - 轨道 ``h-6 w-11 rounded-full``，关 ``bg-gray-200 / dark:bg-white/10``，
 *   开 ``bg-brand-500``；
 * - 圆形拨头 ``size-5``，关 ``translate-x-0.5``，开 ``translate-x-[1.375rem]``，
 *   `transition` 过渡；
 * - label 在左、toggle 在右，整块为 ``inline-flex items-center gap-3`` 的内联
 *   按钮，不再包一层带边框的"卡片"。``description`` 作为 ``title`` tooltip。
 */
const SwitchField = defineComponent({
  props: {
    modelValue: { type: Boolean, required: true },
    label: { type: String, required: true },
    description: { type: String, default: '' },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          role: 'switch',
          'aria-checked': props.modelValue,
          class:
            'inline-flex items-center gap-3 rounded-md px-1 py-1 text-left transition hover:bg-gray-50 dark:hover:bg-white/[0.04]',
          onClick: () => emit('update:modelValue', !props.modelValue),
          title: props.description || undefined,
        },
        [
          h('span', { class: 'text-theme-sm font-medium text-gray-800 dark:text-white/90' }, props.label),
          h(
            'span',
            {
              class: [
                'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200',
                props.modelValue ? 'bg-brand-500' : 'bg-gray-200 dark:bg-white/10',
              ],
            },
            [
              h('span', {
                class: [
                  'inline-block size-5 rounded-full bg-white shadow-theme-xs transition-transform duration-200',
                  props.modelValue ? 'translate-x-[1.375rem]' : 'translate-x-0.5',
                ],
              }),
            ],
          ),
        ],
      )
  },
})

const SegmentedControl = defineComponent({
  props: {
    modelValue: { type: String, required: true },
    items: {
      type: Array as () => Array<{ label: string; value: string }>,
      required: true,
    },
  },
  emits: ['update:modelValue', 'change'],
  setup(props, { emit }) {
    return () =>
      h(
        'div',
        { class: 'inline-flex w-full rounded-lg bg-gray-100 p-1 dark:bg-gray-800' },
        props.items.map((item) =>
          h(
            'button',
            {
              type: 'button',
              class: [
                'flex-1 rounded-md px-3 py-2 text-theme-sm font-medium transition',
                props.modelValue === item.value
                  ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-900 dark:text-white'
                  : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-white/90',
              ],
              onClick: () => {
                emit('update:modelValue', item.value)
                emit('change')
              },
            },
            item.label,
          ),
        ),
      )
  },
})

const SuggestPanel = defineComponent({
  props: {
    items: { type: Array as () => SuggestItem[], required: true },
    loading: { type: Boolean, required: true },
    emptyLabel: { type: String, required: true },
    targetType: { type: String as () => 'playlist' | 'album' | 'artist', required: true },
    selectedId: { type: String, default: '' },
  },
  emits: ['pick'],
  setup(props, { emit }) {
    const fallbackLabel = () =>
      props.targetType === 'artist' ? '艺' : props.targetType === 'album' ? '专' : '歌'
    const metaLine = (it: SuggestItem) => {
      if (props.targetType === 'artist') {
        return [
          it.song_count ? `${formatNum(it.song_count)} 首` : '',
          it.album_count ? `${it.album_count} 专辑` : '',
          it.alias?.length ? it.alias.join(' / ') : '',
        ]
          .filter(Boolean)
          .join(' · ')
      }
      if (props.targetType === 'album') {
        return [
          (it.artists || []).join(' / '),
          it.publish_date || '',
          it.track_count ? `${it.track_count} 首` : '',
        ]
          .filter(Boolean)
          .join(' · ')
      }
      return [
        it.creator || '',
        it.track_count ? `${it.track_count} 首` : '',
        it.play_count ? `${formatNum(it.play_count)} 播放` : '',
      ]
        .filter(Boolean)
        .join(' · ')
    }
    return () =>
      h(
        'div',
        {
          class:
            'absolute z-30 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-gray-200 bg-white p-1 shadow-theme-lg dark:border-gray-800 dark:bg-gray-900',
        },
        props.loading
          ? h('div', { class: 'px-4 py-5 text-center text-theme-sm text-gray-500 dark:text-gray-400' }, '搜索中...')
          : props.items.length
            ? props.items.map((it) =>
                h(
                  'button',
                  {
                    type: 'button',
                    class: [
                      'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition hover:bg-gray-50 dark:hover:bg-white/[0.03]',
                      props.selectedId === it.id ? 'bg-brand-50 dark:bg-brand-500/10' : '',
                    ],
                    onClick: () => emit('pick', it),
                  },
                  [
                    h(
                      'span',
                      {
                        class:
                          'flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-gray-100 text-theme-sm font-semibold text-gray-500 dark:bg-white/5 dark:text-gray-400',
                      },
                      it.cover_url
                        ? h('img', {
                            src: it.cover_url,
                            alt: it.name,
                            loading: 'lazy',
                            class: 'size-full object-cover',
                          })
                        : fallbackLabel(),
                    ),
                    h('span', { class: 'min-w-0' }, [
                      h('span', { class: 'block truncate text-theme-sm font-medium text-gray-800 dark:text-white/90' }, it.name),
                      h('span', { class: 'mt-0.5 block truncate text-theme-xs text-gray-500 dark:text-gray-400' }, metaLine(it)),
                    ]),
                  ],
                ),
              )
            : h('div', { class: 'px-4 py-5 text-center text-theme-sm text-gray-500 dark:text-gray-400' }, props.emptyLabel),
      )
  },
})

// ===== 状态 =====
const items = ref<SubscriptionItem[]>([])
const loading = ref(false)
const syncingAll = ref(false)
const regening = ref(false)
const showAdd = ref(false)
const adding = ref(false)
const confirmDelete = ref<SubscriptionItem | null>(null)
const deleteChildAction = ref<'delete' | 'promote'>('delete')
const confirmHotBulk = ref(false)
/** 动态热门分类订阅表单（POST /subscriptions/hot-category）；
 *  ``sync_interval_hours / enabled / generate_m3u`` 已并入 globalCfg。 */
const hotCat = ref({
  platform: 'netease' as 'netease' | 'qq',
  categories: [] as string[],
  pick_mode: 'top_play_count' as 'top_play_count' | 'random',
  drop_policy: 'keep_history' as 'strict' | 'keep_history',
  top_n: 5,
  pool_size: 50,
})
const hotCatCategoryOptions = ref<string[]>([])
const hotCatCategoriesLoading = ref(false)
const HOTCAT_ACTION_LABELS = new Set(['全部', '全部分类', '全选'])
/** 超过该数量时二次确认，避免一次性创建过多父订阅和下载任务。 */
const HOTCAT_BULK_CONFIRM_THRESHOLD = 10
const normalizedHotTopN = computed(() => Math.max(1, Math.min(30, Number(hotCat.value.top_n) || 5)))
const normalizedHotPoolSize = computed(() =>
  Math.max(normalizedHotTopN.value, Math.min(100, Number(hotCat.value.pool_size) || 50)),
)
const estimatedHotChildCount = computed(() => hotCat.value.categories.length * normalizedHotTopN.value)
const hotBulkConfirmMessage = computed(
  () =>
    `你选择了 ${hotCat.value.categories.length} 个分类，将创建 ${hotCat.value.categories.length} 个动态热门父订阅；每类 Top${normalizedHotTopN.value}，预计最多维护 ${estimatedHotChildCount.value} 个热门子歌单。确认继续吗？`,
)
const hotCategoryMeta = (category: string) => {
  const text = category.trim()
  const match = text.match(/^(.+?)\s*[·・]\s*(.+)$/)
  if (!match) return { group: '分类', label: text }
  return { group: match[1].trim() || '分类', label: match[2].trim() || text }
}
const hotCategoryLabel = (category: string) => hotCategoryMeta(category).label
const hasUnselectedHotCategories = computed(() =>
  hotCatCategoryOptions.value.some((category) => !hotCat.value.categories.includes(category)),
)
const hotCatCategoryGroups = computed(() => {
  const groups = new Map<string, string[]>()
  for (const category of hotCatCategoryOptions.value) {
    const group = hotCategoryMeta(category).group
    groups.set(group, [...(groups.get(group) ?? []), category])
  }
  return Array.from(groups, ([name, items]) => ({ name, items }))
})
const message = useMusicToast()
const router = useRouter()

const selectAllHotCategories = () => {
  hotCat.value.categories = Array.from(new Set([...hotCat.value.categories, ...hotCatCategoryOptions.value]))
}

const toggleHotCategory = (category: string) => {
  if (hotCat.value.categories.includes(category)) {
    hotCat.value.categories = hotCat.value.categories.filter((item) => item !== category)
    return
  }
  hotCat.value.categories = [...hotCat.value.categories, category]
}

const loadHotCategoryOptions = async () => {
  hotCatCategoriesLoading.value = true
  try {
    const items = await discoverApi.hotPlaylistCategories(hotCat.value.platform)
    const categoryItems = items.filter((item) => !HOTCAT_ACTION_LABELS.has(item.trim()))
    hotCatCategoryOptions.value = categoryItems
    hotCat.value.categories = hotCat.value.categories.filter((c) => categoryItems.includes(c))
  } catch {
    hotCatCategoryOptions.value = []
    message.error('加载分类列表失败')
  } finally {
    hotCatCategoriesLoading.value = false
  }
}

watch(
  () => hotCat.value.platform,
  () => {
    hotCat.value.categories = []
    void loadHotCategoryOptions()
  },
)

const search = ref('')
const filterPlatform = ref<'all' | 'netease' | 'qq'>('all')
const filterKind = ref<'all' | 'playlist' | 'album' | 'artist' | 'meta' | 'daily'>('all')
const hideAutoAdded = ref(true)
const page = ref(1)
const pageSize = 30

const platformOptions = [
  { label: '全部平台', value: 'all' },
  { label: '网易云', value: 'netease' },
  { label: 'QQ 音乐', value: 'qq' },
]
const kindOptions = [
  { label: '全部类型', value: 'all' },
  { label: '歌单', value: 'playlist' },
  { label: '专辑', value: 'album' },
  { label: '歌手', value: 'artist' },
  { label: 'Meta', value: 'meta' },
  { label: '每日推荐', value: 'daily' },
]

// ===== 列表过滤/分页 =====
const filteredItems = computed(() => {
  const q = search.value.trim().toLowerCase()
  return items.value.filter((s) => {
    if (filterPlatform.value !== 'all' && s.platform !== filterPlatform.value) return false
    if (filterKind.value !== 'all') {
      if (filterKind.value === 'meta' && !s.target_type.startsWith('meta_')) return false
      if (filterKind.value === 'playlist' && s.target_type !== 'playlist') return false
      if (filterKind.value === 'album' && s.target_type !== 'album') return false
      if (filterKind.value === 'artist' && s.target_type !== 'artist') return false
      if (filterKind.value === 'daily' && s.target_type !== 'daily') return false
    }
    if (hideAutoAdded.value && s.auto_added) return false
    if (q) {
      const hay = `${s.name} ${s.creator || ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})
const pageCount = computed(() =>
  Math.max(1, Math.ceil(filteredItems.value.length / pageSize)),
)
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredItems.value.slice(start, start + pageSize)
})
watch([search, filterPlatform, filterKind, hideAutoAdded], () => {
  page.value = 1
})

// ===== 添加表单（同步间隔/启用/m3u8 已迁出至 globalCfg） =====
// 单一输入框 ``searchQuery`` 同时承担"关键词搜索 + ID/URL 直填"双职责：
// - 输入命中 ID/URL 模式时跳过搜索建议，``customId`` 自动识别；
// - 否则发起 suggest 搜索，用户从下拉里挑选条目（赋值 ``id`` + ``pickedName``）。
const form = ref({
  platform: 'netease' as 'netease' | 'qq',
  target_type: 'playlist' as 'playlist' | 'album' | 'artist',
  id: '',
  searchQuery: '',
  pickedName: '',
  cross_platform: false,
  cross_platform_id: '',
  crossSearchQuery: '',
  crossPickedName: '',
})

/**
 * 全局配置：modal 顶部一组，三类订阅（动态热门 / 一键订阅 / 自定义）共用。
 *
 * - sync_interval_hours：每个订阅的定时同步周期（小时）。
 * - enabled：创建后是否立即启用调度。
 * - generate_m3u：歌单类是否生成 _m3u/*.m3u8 播放列表。
 */
const globalCfg = ref({
  sync_interval_hours: 24,
  enabled: true,
  generate_m3u: true,
})

/**
 * 三块手风琴互斥状态：同时只展开一个。``null`` 表示全部收起。
 * - 受控的 ``<details :open="accordion === 'xxx'">`` + ``@click.prevent="toggleAcc(...)"``。
 */
const accordion = ref<'hot' | 'quick' | 'custom' | null>('hot')
const toggleAcc = (key: 'hot' | 'quick' | 'custom') => {
  accordion.value = accordion.value === key ? null : key
}

/**
 * 一键订阅：纯"选择"模式（不再点击立即提交）。
 * key 形如 ``daily__netease`` / ``toplists_all__qq``，由 ``${kind}__${platform}`` 拼接。
 * 已订阅项不可勾选（``existingMap`` 命中），由底部「添加」一次性提交剩余勾选。
 */
const quickPicked = ref<Set<string>>(new Set())
const quickKey = (q: { kind: string; platform: string }) => `${q.kind}__${q.platform}`
const isQuickPicked = (q: { kind: string; platform: string }) => quickPicked.value.has(quickKey(q))
const toggleQuickPick = (q: { kind: QuickSubscribeKind; platform: 'netease' | 'qq'; existingKey: string }) => {
  if (existingMap.value.has(q.existingKey)) return
  const k = quickKey(q)
  const next = new Set(quickPicked.value)
  if (next.has(k)) next.delete(k)
  else next.add(k)
  quickPicked.value = next
}

const otherPlatformLabel = computed(() =>
  form.value.platform === 'netease' ? 'QQ 音乐' : '网易云',
)
const otherPlatformKey = computed<'netease' | 'qq'>(() =>
  form.value.platform === 'netease' ? 'qq' : 'netease',
)

const crossSuggestItems = ref<SuggestItem[]>([])
const crossSuggestLoading = ref(false)
const crossSuggestOpen = ref(false)
let crossSuggestTimer: number | null = null
let crossSuggestSeq = 0

const onCrossSearchInput = () => {
  form.value.cross_platform_id = ''
  form.value.crossPickedName = ''
  if (crossSuggestTimer) clearTimeout(crossSuggestTimer)
  const q = form.value.crossSearchQuery.trim()
  if (!q) {
    crossSuggestItems.value = []
    crossSuggestOpen.value = false
    return
  }
  crossSuggestOpen.value = true
  crossSuggestLoading.value = true
  const seq = ++crossSuggestSeq
  crossSuggestTimer = window.setTimeout(async () => {
    try {
      const kind = form.value.target_type === 'artist' ? 'artist' : 'album'
      const list = await discoverApi.suggest(kind, q, otherPlatformKey.value)
      if (seq !== crossSuggestSeq) return
      crossSuggestItems.value = list
    } catch {
      if (seq !== crossSuggestSeq) return
      crossSuggestItems.value = []
    } finally {
      if (seq === crossSuggestSeq) crossSuggestLoading.value = false
    }
  }, 300)
}

const onCrossSearchFocus = () => {
  if (form.value.crossSearchQuery.trim()) crossSuggestOpen.value = true
}

const startCrossSearchFromPrimary = () => {
  if (form.value.target_type !== 'artist' && form.value.target_type !== 'album') return
  const name = (form.value.pickedName || form.value.searchQuery).trim()
  if (!name || looksLikeIdOrUrl(name)) {
    crossSuggestItems.value = []
    crossSuggestOpen.value = false
    return
  }
  form.value.cross_platform_id = ''
  form.value.crossPickedName = ''
  form.value.crossSearchQuery = name
  onCrossSearchInput()
}

const pickCrossSuggest = (it: SuggestItem) => {
  form.value.cross_platform_id = it.id
  form.value.crossPickedName = it.name
  form.value.crossSearchQuery = it.name
  crossSuggestOpen.value = false
}

const clearCrossPick = () => {
  form.value.cross_platform_id = ''
  form.value.crossPickedName = ''
  form.value.crossSearchQuery = ''
  crossSuggestItems.value = []
  crossSuggestOpen.value = false
}

const clearPrimaryPick = () => {
  form.value.id = ''
  form.value.pickedName = ''
  form.value.searchQuery = ''
  form.value.cross_platform = false
  clearCrossPick()
  suggestItems.value = []
  suggestOpen.value = false
}

const suggestItems = ref<SuggestItem[]>([])
const suggestLoading = ref(false)
const suggestOpen = ref(false)
let suggestTimer: number | null = null
let suggestSeq = 0

const searchLabel = computed(() => {
  const t = form.value.target_type === 'artist' ? '歌手' : form.value.target_type === 'album' ? '专辑' : '歌单'
  return `搜索${t}，或直接粘贴 ID / URL`
})
const searchPlaceholder = computed(() => {
  const t = form.value.target_type === 'artist' ? '歌手' : form.value.target_type === 'album' ? '专辑' : '歌单'
  return `输入${t}名搜索；或粘贴 19723756 / https://music.163.com/playlist?id=19723756`
})
const pickedLabel = computed(() => form.value.pickedName || '')

/** 判断输入是否更像「ID 或 URL」而非搜索关键词；命中则跳过 suggest，直接用 extractId 识别。 */
const looksLikeIdOrUrl = (raw: string): boolean => {
  const s = raw.trim()
  if (!s) return false
  if (/^\d{4,}$/.test(s)) return true
  if (extractId(s) !== s) return true
  return false
}

/** 当前自定义订阅的目标 ID：优先来自 suggest 选中，否则尝试从输入里识别 ID/URL。 */
const customId = computed(() => {
  if (form.value.id) return form.value.id
  const raw = form.value.searchQuery.trim()
  if (raw && looksLikeIdOrUrl(raw)) return extractId(raw)
  return ''
})

watch(
  () => form.value.cross_platform,
  (enabled) => {
    if (!enabled) {
      clearCrossPick()
      return
    }
    if (!form.value.id || !form.value.pickedName) {
      message.warning('请先在主平台搜索并选择歌手或专辑，再开启全平台聚合')
      form.value.cross_platform = false
      return
    }
    startCrossSearchFromPrimary()
  },
)

const formatNum = (n: number) => {
  if (n >= 100_000_000) return `${(n / 100_000_000).toFixed(1)}亿`
  if (n >= 10_000) return `${(n / 10_000).toFixed(1)}万`
  return String(n)
}

const onSearchInput = () => {
  form.value.id = ''
  form.value.pickedName = ''
  if (suggestTimer) clearTimeout(suggestTimer)
  const q = form.value.searchQuery.trim()
  if (!q) {
    suggestItems.value = []
    suggestOpen.value = false
    return
  }
  // 输入是 ID/URL：跳过搜索建议，customId computed 会自动识别
  if (looksLikeIdOrUrl(q)) {
    suggestItems.value = []
    suggestOpen.value = false
    suggestLoading.value = false
    return
  }
  suggestOpen.value = true
  suggestLoading.value = true
  const seq = ++suggestSeq
  suggestTimer = window.setTimeout(async () => {
    try {
      const list = await discoverApi.suggest(
        form.value.target_type,
        q,
        form.value.platform,
      )
      if (seq !== suggestSeq) return
      suggestItems.value = list
    } catch {
      if (seq !== suggestSeq) return
      suggestItems.value = []
    } finally {
      if (seq === suggestSeq) suggestLoading.value = false
    }
  }, 300)
}

const onSearchFocus = () => {
  const q = form.value.searchQuery.trim()
  if (!q) return
  if (looksLikeIdOrUrl(q)) return
  suggestOpen.value = true
}

const onPlatformOrTypeChange = () => {
  form.value.id = ''
  form.value.pickedName = ''
  suggestItems.value = []
  form.value.cross_platform_id = ''
  form.value.crossPickedName = ''
  form.value.crossSearchQuery = ''
  crossSuggestItems.value = []
  crossSuggestOpen.value = false
  if (form.value.searchQuery.trim()) onSearchInput()
}

const pickSuggest = (it: SuggestItem) => {
  form.value.id = it.id
  form.value.pickedName = it.name
  form.value.searchQuery = it.name
  suggestOpen.value = false
  if (form.value.cross_platform && (form.value.target_type === 'artist' || form.value.target_type === 'album')) {
    startCrossSearchFromPrimary()
  }
}

const resetAddForm = () => {
  form.value.id = ''
  form.value.searchQuery = ''
  form.value.pickedName = ''
  form.value.cross_platform = false
  form.value.cross_platform_id = ''
  form.value.crossSearchQuery = ''
  form.value.crossPickedName = ''
  suggestItems.value = []
  suggestOpen.value = false
  crossSuggestItems.value = []
  crossSuggestOpen.value = false
}

watch(showAdd, (open) => {
  if (!open) {
    resetAddForm()
  } else {
    accordion.value = 'hot'
    quickPicked.value = new Set()
    hotCat.value.categories = []
    hotCat.value.pick_mode = 'top_play_count'
    hotCat.value.drop_policy = 'keep_history'
    hotCat.value.top_n = 5
    hotCat.value.pool_size = 50
    globalCfg.value = { sync_interval_hours: 24, enabled: true, generate_m3u: true }
    void loadHotCategoryOptions()
  }
})

/** 自定义添加 summary 的"已选"摘要：仅当选中或填了 ID/URL 时展示 */
const customPickedSummary = computed(() => {
  if (form.value.id && form.value.pickedName) return `已选 ${form.value.pickedName}`
  if (customId.value) return `识别 ID ${customId.value}`
  return ''
})

// 自动添加订阅数量（用于"订阅明细"标题副文字 + 空状态提示）
const autoAddedCount = computed(() => items.value.filter((s) => s.auto_added).length)

// ===== Row 4 左：同步活跃度趋势图 =====
const activityTabs = [
  { key: '14d' as const, label: '14 天' },
  { key: '7d' as const, label: '7 天' },
  { key: 'all' as const, label: '全部' },
]
type ActivityTabKey = (typeof activityTabs)[number]['key']
const activityTab = ref<ActivityTabKey>('14d')

const activityRangeLabel = computed(() => {
  if (activityTab.value === '7d') return '近 7 天'
  if (activityTab.value === 'all') return '历史'
  return '近 14 天'
})

const activityWindowDays = computed(() => {
  if (activityTab.value === '7d') return 7
  if (activityTab.value === 'all') return 60
  return 14
})

interface DailyAggr {
  date: string
  count: number
}

const dailyActivity = computed<DailyAggr[]>(() => {
  const days = activityWindowDays.value
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const map = new Map<string, number>()
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400_000)
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    map.set(k, 0)
  }
  for (const s of items.value) {
    if (!s.last_sync_at) continue
    const d = new Date(s.last_sync_at)
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    if (map.has(k)) {
      map.set(k, (map.get(k) || 0) + Math.max(1, s.last_sync_new_count || 1))
    }
  }
  return [...map.entries()].map(([date, count]) => ({ date, count }))
})

const ACT_W = 600
const ACT_H = 190
const ACT_TOP = 16
const ACT_BOTTOM = 16

interface ChartPoint {
  x: number
  y: number
  value: number
  date: string
}

const activityChart = computed(() => {
  const src = dailyActivity.value
  if (!src.length || src.every((d) => d.count === 0)) {
    return { points: [] as ChartPoint[], line: '', area: '' }
  }
  const max = Math.max(...src.map((d) => d.count), 1)
  const usableH = ACT_H - ACT_TOP - ACT_BOTTOM
  const points: ChartPoint[] = src.map((d, idx) => ({
    x: src.length === 1 ? ACT_W / 2 : (idx / (src.length - 1)) * ACT_W,
    y: ACT_TOP + usableH - (d.count / max) * usableH,
    value: d.count,
    date: d.date,
  }))
  let line = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`
  for (let i = 0; i < points.length - 1; i++) {
    const cur = points[i]
    const next = points[i + 1]
    const cx = (cur.x + next.x) / 2
    line += ` C ${cx.toFixed(1)},${cur.y.toFixed(1)} ${cx.toFixed(1)},${next.y.toFixed(1)} ${next.x.toFixed(1)},${next.y.toFixed(1)}`
  }
  const area = `${line} L ${points[points.length - 1].x.toFixed(1)},${ACT_H} L ${points[0].x.toFixed(1)},${ACT_H} Z`
  return { points, line, area }
})

const activityGridLines = computed(() => {
  const lines = []
  for (let i = 0; i <= 4; i++) {
    lines.push({ y: ACT_TOP + ((ACT_H - ACT_TOP - ACT_BOTTOM) * i) / 4 })
  }
  return lines
})

const activityXLabels = computed(() => {
  const src = dailyActivity.value
  if (!src.length) return []
  if (src.length <= 7) return src.map((d) => d.date.slice(5))
  const ticks = 7
  const step = (src.length - 1) / (ticks - 1)
  return Array.from({ length: ticks }, (_, i) => src[Math.round(i * step)].date.slice(5))
})

// ===== Row 2 右：来源构成（平台 + 类型） =====
const platformBreakdown = computed(() => {
  const total = items.value.length || 1
  const map: Record<string, number> = {}
  for (const s of items.value) {
    map[s.platform] = (map[s.platform] || 0) + 1
  }
  return (['netease', 'qq'] as const).map((k) => ({
    key: k,
    label: k === 'netease' ? '网易云音乐' : 'QQ 音乐',
    value: map[k] || 0,
    pct: Math.round(((map[k] || 0) / total) * 100),
  }))
})

interface TypeRow {
  key: string
  label: string
  value: number
  pct: number
  icon: Component
  toneClass: string
  color: 'brand' | 'success' | 'warning' | 'info' | 'error'
}

const typeBreakdown = computed<TypeRow[]>(() => {
  // 计算时把 meta_* 拆成 我创建 / 我收藏 / 排行榜 / 其他 Meta 四个桶，
  // 避免之前所有 meta_* 被合并成单一"Meta 跟随"导致的统计失真。
  const total = items.value.length || 1
  const counter = (pred: (s: SubscriptionItem) => boolean) => items.value.filter(pred).length
  const pct = (n: number) => (total ? Math.round((n / total) * 100) : 0)

  const playlist = counter((s) => s.target_type === 'playlist')
  const album = counter((s) => s.target_type === 'album')
  const artist = counter((s) => s.target_type === 'artist')
  const metaCreated = counter((s) => s.target_type === 'meta_my_created')
  const metaCollected = counter((s) => s.target_type === 'meta_my_collected')
  const metaToplists = counter((s) => s.target_type === 'meta_toplists')
  const metaOther = counter(
    (s) =>
      s.target_type.startsWith('meta_') &&
      s.target_type !== 'meta_my_created' &&
      s.target_type !== 'meta_my_collected' &&
      s.target_type !== 'meta_toplists',
  )
  const daily = counter((s) => s.target_type === 'daily')

  const rows: TypeRow[] = [
    {
      key: 'playlist',
      label: '歌单',
      value: playlist,
      pct: pct(playlist),
      icon: ListMusic,
      toneClass: 'bg-gray-100 text-gray-600 dark:bg-white/5 dark:text-gray-300',
      color: 'brand',
    },
    {
      key: 'meta_my_created',
      label: '我创建的歌单',
      value: metaCreated,
      pct: pct(metaCreated),
      icon: Pencil,
      toneClass: 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500',
      color: 'success',
    },
    {
      key: 'meta_my_collected',
      label: '我收藏的歌单',
      value: metaCollected,
      pct: pct(metaCollected),
      icon: Heart,
      toneClass: 'bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500',
      color: 'error',
    },
    {
      key: 'meta_toplists',
      label: '排行榜',
      value: metaToplists,
      pct: pct(metaToplists),
      icon: Trophy,
      toneClass: 'bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400',
      color: 'warning',
    },
    {
      key: 'meta_other',
      label: '其他 Meta',
      value: metaOther,
      pct: pct(metaOther),
      icon: Layers,
      toneClass: 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500',
      color: 'success',
    },
    {
      key: 'album',
      label: '专辑',
      value: album,
      pct: pct(album),
      icon: Disc3,
      toneClass: 'bg-brand-50 text-brand-500 dark:bg-brand-500/15 dark:text-brand-400',
      color: 'brand',
    },
    {
      key: 'artist',
      label: '歌手',
      value: artist,
      pct: pct(artist),
      icon: UserRound,
      toneClass: 'bg-warning-50 text-warning-600 dark:bg-warning-500/15 dark:text-orange-400',
      color: 'warning',
    },
    {
      key: 'daily',
      label: '每日推荐',
      value: daily,
      pct: pct(daily),
      icon: Sun,
      toneClass: 'bg-blue-light-50 text-blue-light-600 dark:bg-blue-light-500/15 dark:text-blue-light-500',
      color: 'info',
    },
  ]
  return rows.filter((r) => r.value > 0)
})

// ===== Row 3 右：同步活动时间线 =====
interface ActivityEvent {
  id: number
  name: string
  detail: string
  timeLabel: string
  dateTitle: string
  icon: Component
  color: string
  bg: string
}

const activities = computed<ActivityEvent[]>(() => {
  const synced = items.value.filter((s) => s.last_sync_at)
  return [...synced]
    .sort(
      (a, b) =>
        new Date(b.last_sync_at!).getTime() - new Date(a.last_sync_at!).getTime(),
    )
    .slice(0, 6)
    .map((s) => {
      const isError = Boolean(s.last_error)
      const newCount = s.last_sync_new_count || 0
      return {
        id: s.id,
        name: s.name,
        detail: isError
          ? `同步失败：${s.last_error}`
          : newCount > 0
            ? `${targetTypeLabel(s.target_type)} · 新增 ${newCount} 首（远端 ${s.last_sync_track_count}）`
            : `${targetTypeLabel(s.target_type)} · 远端 ${s.last_sync_track_count} 首，无新增`,
        timeLabel: relativeTime(s.last_sync_at!),
        dateTitle: formatDt(s.last_sync_at!),
        icon: isError ? XCircle : newCount > 0 ? CheckCircle2 : AlertCircle,
        color: isError
          ? 'text-error-600 dark:text-error-500'
          : newCount > 0
            ? 'text-success-600 dark:text-success-500'
            : 'text-gray-500 dark:text-gray-400',
        bg: isError
          ? 'bg-error-50 dark:bg-error-500/15'
          : newCount > 0
            ? 'bg-success-50 dark:bg-success-500/15'
            : 'bg-gray-100 dark:bg-white/5',
      }
    })
})

// ===== 快速订阅 =====
const existingMap = computed(() => {
  const m = new Map<string, SubscriptionItem>()
  for (const s of items.value) {
    m.set(`${s.platform}-${s.platform_playlist_id}`, s)
  }
  return m
})

const PLATFORMS = [
  { key: 'netease', label: '网易云' },
  { key: 'qq', label: 'QQ 音乐' },
] as const

const GROUP_META: Array<{
  kind: QuickSubscribeKind
  label: string
  description: string
  tag: string
  tagType: 'success' | 'info'
  icon: Component
  cardDesc: string
  existingSuffix: string
}> = [
  {
    kind: 'daily',
    label: '每日推荐',
    description: '每天自动抓取平台推荐歌曲并入队下载',
    tag: '虚拟',
    tagType: 'info',
    icon: Sun,
    cardDesc: '今日推荐歌曲',
    existingSuffix: 'daily',
  },
  {
    kind: 'toplists_all',
    label: '官方排行榜',
    description: '一键订阅全部官方榜单（meta 自动跟随）',
    tag: 'meta',
    tagType: 'success',
    icon: Trophy,
    cardDesc: '飙升 / 新歌 / 热歌',
    existingSuffix: 'meta_toplists',
  },
  {
    kind: 'follow_my_created',
    label: '我创建的歌单',
    description: '跟随我创建的歌单（含「我喜欢的」红心）',
    tag: 'meta',
    tagType: 'success',
    icon: Pencil,
    cardDesc: '我创建的歌单',
    existingSuffix: 'meta_my_created',
  },
  {
    kind: 'follow_my_collected',
    label: '我收藏的歌单',
    description: '跟随我收藏的他人歌单',
    tag: 'meta',
    tagType: 'success',
    icon: Heart,
    cardDesc: '我收藏的歌单',
    existingSuffix: 'meta_my_collected',
  },
]

const quickGroups = computed<QuickGroup[]>(() =>
  GROUP_META.map((g) => ({
    kind: g.kind,
    label: g.label,
    description: g.description,
    tag: g.tag,
    tagType: g.tagType,
    icon: g.icon,
    items: PLATFORMS.map((p) => ({
      kind: g.kind,
      platform: p.key,
      platformLabel: p.label,
      title: p.label,
      description: g.cardDesc,
      existingKey: `${p.key}-${g.existingSuffix}`,
    })),
  })),
)

// ===== 业务方法 =====
const refresh = async () => {
  loading.value = true
  try {
    items.value = await subscriptionsApi.list()
  } catch (e: any) {
    message.error(`加载失败：${e?.message ?? e}`)
  } finally {
    loading.value = false
  }
}

const onSyncOne = async (id: number) => {
  try {
    const r = await subscriptionsApi.syncNow(id)
    if (r.error) {
      message.error(`同步失败：${r.error}`)
    } else {
      message.success(
        `${r.name}：远端 ${r.remote_count} 首，新增 ${r.new_count}（新入队 ${r.enqueued} 首，复用队列 ${r.already_queued || 0} 首）`,
      )
    }
    await refresh()
  } catch (e: any) {
    message.error(`同步失败：${e?.message ?? e}`)
  }
}

const extractId = (raw: string): string => {
  const s = raw.trim()
  if (!s) return s
  const m1 = s.match(/[?&]id=(\d+)/)
  if (m1) return m1[1]
  const m2 = s.match(/\/(?:playlist|album|songDetail)\/([\w]+)/i)
  if (m2) return m2[1]
  return s
}

/**
 * 添加按钮：一次性提交三类订阅（动态热门 / 一键订阅勾选项 / 自定义）。
 *
 * 任一类有内容即生效；若全部为空则提示。三类共用 ``globalCfg`` 的
 * 同步间隔 / 立即启用 / 生成 m3u8。
 */
const submitAll = async () => {
  const hasHot = hotCat.value.categories.length > 0
  if (hasHot && hotCat.value.categories.length >= HOTCAT_BULK_CONFIRM_THRESHOLD) {
    confirmHotBulk.value = true
    return
  }
  await submitAllConfirmed()
}

const submitAllConfirmed = async () => {
  confirmHotBulk.value = false
  const hasHot = hotCat.value.categories.length > 0
  const hasQuick = quickPicked.value.size > 0
  const customSubmitId = customId.value
  const hasCustom = Boolean(customSubmitId)
  if (!hasHot && !hasQuick && !hasCustom) {
    message.warning('请至少选择一项再添加')
    return
  }

  adding.value = true
  let okCnt = 0
  const failed: string[] = []
  try {
    if (hasHot) {
      const topN = normalizedHotTopN.value
      const poolSize = normalizedHotPoolSize.value
      for (const category of hotCat.value.categories) {
        try {
          const r = await subscriptionsApi.addHotCategory({
            platform: hotCat.value.platform,
            categories: [category],
            pick_mode: hotCat.value.pick_mode,
            drop_policy: hotCat.value.drop_policy,
            top_n: topN,
            pool_size: poolSize,
            sync_interval_hours: globalCfg.value.sync_interval_hours,
            enabled: globalCfg.value.enabled,
            generate_m3u: globalCfg.value.generate_m3u,
          })
          okCnt++
          message.success(`已添加：${r.name}`)
        } catch (e: any) {
          failed.push(`动态热门-${category}：${e?.response?.data?.detail || e?.message || e}`)
        }
      }
    }

    for (const k of quickPicked.value) {
      const [kind, platform] = k.split('__') as [QuickSubscribeKind, 'netease' | 'qq']
      try {
        await subscriptionsApi.quickAdd({
          kind,
          platform,
          sync_interval_hours: globalCfg.value.sync_interval_hours,
          enabled: globalCfg.value.enabled,
          generate_m3u: globalCfg.value.generate_m3u,
        })
        okCnt++
      } catch (e: any) {
        if (e?.response?.status === 409) {
          okCnt++
        } else {
          failed.push(`${platform}-${kind}：${e?.response?.data?.detail || e?.message || e}`)
        }
      }
    }

    if (hasCustom) {
      try {
        const r = await subscriptionsApi.add({
          platform: form.value.platform,
          target_type: form.value.target_type,
          id: customSubmitId,
          sync_interval_hours: globalCfg.value.sync_interval_hours,
          enabled: globalCfg.value.enabled,
          generate_m3u: globalCfg.value.generate_m3u,
          cross_platform: form.value.cross_platform,
          cross_platform_id: form.value.cross_platform_id || undefined,
        })
        okCnt++
        message.success(`已添加：${r.name}`)
      } catch (e: any) {
        failed.push(`自定义：${e?.response?.data?.detail || e?.message || e}`)
      }
    }

    if (okCnt && !failed.length) {
      if (okCnt > 1) message.success(`共添加 ${okCnt} 个订阅`)
      showAdd.value = false
      resetAddForm()
    }
    if (failed.length) {
      message.error(failed.join('；'))
    }
    await refresh()
  } finally {
    adding.value = false
  }
}

const syncAll = async () => {
  syncingAll.value = true
  try {
    const batch = await subscriptionsApi.syncAll()
    message.success('全部同步已开始，后台会继续处理')
    let current = batch
    for (let i = 0; i < 120 && current.status === 'running'; i++) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000))
      current = await subscriptionsApi.syncAllStatus(batch.id)
    }
    if (current.status === 'completed') {
      const reused = current.already_queued ? `，复用队列 ${current.already_queued} 首` : ''
      message.success(`全部同步完成，新入队 ${current.enqueued} 首${reused}`)
    } else if (current.status === 'failed') {
      message.error(`全部同步失败：${current.error || '未知错误'}`)
    }
    await refresh()
  } catch (e: any) {
    message.error(`同步失败：${e?.message ?? e}`)
  } finally {
    syncingAll.value = false
  }
}

const regenAll = async () => {
  regening.value = true
  try {
    const r = await subscriptionsApi.generateM3UAll()
    message.success(`已生成 ${r.generated} 个 m3u8 文件`)
  } catch (e: any) {
    message.error(`生成失败：${e?.message ?? e}`)
  } finally {
    regening.value = false
  }
}

const childCountOf = (sub: SubscriptionItem) =>
  items.value.filter((item) => item.parent_subscription_id === sub.id && item.auto_added).length

const deleteTip = (sub: SubscriptionItem) => {
  if (sub.target_type.startsWith('meta_')) {
    const count = childCountOf(sub)
    return count
      ? `将同时删除 ${count} 个自动子订阅。`
      : '没有归属到它的自动子订阅。'
  }
  if (sub.auto_added && sub.parent_subscription_id) return '这是父级来源维护的子订阅；删除后父级下次同步可能重新创建。'
  if (sub.auto_added) return '这是旧版未归属自动订阅；删除后不会自动关联到父级。'
  return '已下载的歌曲不会被删除。'
}

const deleteConfirmMessage = computed(() =>
  confirmDelete.value
    ? `确定要删除「${confirmDelete.value.name}」吗？${deleteTip(confirmDelete.value)}`
    : '',
)

const removeOne = (sub: SubscriptionItem) => {
  deleteChildAction.value = 'delete'
  confirmDelete.value = sub
}

const confirmRemove = async () => {
  const sub = confirmDelete.value
  if (!sub) return
  try {
    await subscriptionsApi.remove(sub.id, deleteChildAction.value)
    message.success('已删除')
    confirmDelete.value = null
    await refresh()
  } catch (e: any) {
    message.error(`删除失败：${e?.message ?? e}`)
  }
}

/**
 * 启用 / 停用 订阅。
 *
 * 设计说明：
 *  - enabledBusy[id] 在请求期间为 true，按钮 disabled + 视觉变灰，避免重复点击造成
 *    "前端先乐观更新→后端 500→前端没回滚"导致状态错乱；
 *  - 采用「先调后端、成功后再改本地状态」的悲观写法，状态与服务端一致；
 *  - 失败时弹 toast 并保持原值不变，用户可立即重试。
 */
const enabledBusy = ref<Record<number, boolean>>({})

const toggleEnabled = async (sub: SubscriptionItem, val: boolean) => {
  if (enabledBusy.value[sub.id]) return
  enabledBusy.value = { ...enabledBusy.value, [sub.id]: true }
  try {
    await subscriptionsApi.update(sub.id, { enabled: val })
    sub.enabled = val
    await refresh()
    message.success(val ? '已启用' : '已停用', 1200)
  } catch (e: any) {
    message.error(`修改失败：${e?.message ?? e}`)
  } finally {
    const next = { ...enabledBusy.value }
    delete next[sub.id]
    enabledBusy.value = next
  }
}

/** 行是否可点击跳详情（仅 playlist / album 单订阅有详情页）。 */
const isRowClickable = (row: SubscriptionItem) =>
  row.target_type === 'playlist' || row.target_type === 'album'

/**
 * 行点击：仅 playlist / album 跳详情；
 * 其它类型直接 no-op，不再绑定无意义的整行事件，减少与子元素事件竞争。
 */
const onRowClick = (row: SubscriptionItem) => {
  if (isRowClickable(row)) gotoDetail(row)
}

const updateInterval = async (sub: SubscriptionItem, val: number) => {
  if (!val || val < 1) return
  try {
    await subscriptionsApi.update(sub.id, { sync_interval_hours: val })
    sub.sync_interval_hours = val
    message.success('已更新同步间隔', 1200)
  } catch (e: any) {
    message.error(`修改失败：${e?.message ?? e}`)
  }
}

// ===== 工具方法 =====
const formatDt = (s: string | null) => {
  if (!s) return '从未同步'
  return new Date(s).toLocaleString('zh-CN')
}

function targetTypeLabel(t: SubscriptionItem['target_type']) {
  switch (t) {
    case 'album':
      return '专辑'
    case 'artist':
      return '歌手'
    case 'daily':
      return '每日推荐'
    case 'meta_my_created':
      return 'meta · 我创建'
    case 'meta_my_collected':
      return 'meta · 我收藏'
    case 'meta_toplists':
      return 'meta · 排行榜'
    case 'meta_hot_category':
      return '热门分类 TopN'
    default:
      return '歌单'
  }
}

function targetTypeColor(t: SubscriptionItem['target_type']) {
  if (t.startsWith('meta_')) return 'success'
  if (t === 'daily') return 'info'
  if (t === 'album') return 'brand'
  if (t === 'artist') return 'warning'
  return 'gray'
}

function rowFallbackIcon(row: SubscriptionItem) {
  if (row.target_type.startsWith('meta_')) return Layers
  if (row.target_type === 'daily') return Sun
  if (row.target_type === 'album') return Disc3
  if (row.target_type === 'artist') return UserRound
  return Music2
}

function relativeTime(s: string) {
  const t = new Date(s).getTime()
  const diff = Date.now() - t
  if (diff < 0) return '刚刚'
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec} 秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return new Date(s).toLocaleDateString('zh-CN')
}

const gotoDetail = (row: SubscriptionItem) => {
  if (row.target_type === 'playlist') {
    router.push({
      name: 'playlist-detail',
      params: { platform: row.platform, id: row.platform_playlist_id },
    })
  } else if (row.target_type === 'album') {
    router.push({
      name: 'album-detail',
      params: { platform: row.platform, id: row.platform_playlist_id },
    })
  }
}

onMounted(() => {
  void refresh()
})
</script>
