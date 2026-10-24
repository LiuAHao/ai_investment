/** 把后端 trace.phases 转成 PhaseProgress 需要的 map */
export function phasesFromTrace(trace) {
  const map = {}
  ;(trace?.phases || []).forEach((item) => {
    if (!item?.phase) return
    map[item.phase] = {
      status: item.degraded ? 'degraded' : 'done',
      duration_ms: item.duration_ms,
      degraded: Boolean(item.degraded),
      detail: item.detail,
    }
  })
  return map
}
