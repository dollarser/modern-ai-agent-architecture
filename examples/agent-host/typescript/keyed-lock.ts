/** 同一进程内的存储作用域互斥；不代替数据库租约。 */
import { resolve } from "node:path"
const objects = new WeakMap<object, number>()
let nextId = 0
export const storeScope = (store: object): string => {
  const path = (store as { path?: string }).path
  if (path !== undefined) return resolve(path)
  if (!objects.has(store)) objects.set(store, ++nextId)
  return `object:${objects.get(store)}`
}
const queues = new Map<string, Promise<void>>()
export const withKeyLock = async <T>(scope: string, identity: string, execute: () => Promise<T>): Promise<T> => {
  const key = JSON.stringify([scope, identity])
  const previous = queues.get(key) ?? Promise.resolve()
  let release!: () => void
  const current = new Promise<void>((resolve) => { release = resolve })
  queues.set(key, current)
  await previous
  try { return await execute() }
  finally {
    release()
    if (queues.get(key) === current) queues.delete(key)
  }
}

const active = new Map<string, Set<Promise<unknown>>>()
export const trackExecution = (scope: string, runId: string, promise: Promise<unknown>): void => {
  const key = JSON.stringify([scope, runId])
  const calls = active.get(key) ?? new Set<Promise<unknown>>()
  calls.add(promise); active.set(key, calls)
  const finished = () => {
    calls.delete(promise)
    if (!calls.size) active.delete(key)
  }
  void promise.then(finished, finished)
}
export const hasActiveExecution = (scope: string, runId: string): boolean =>
  !!active.get(JSON.stringify([scope, runId]))?.size
