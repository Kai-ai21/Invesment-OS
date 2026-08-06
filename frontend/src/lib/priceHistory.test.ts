import { beforeEach, expect, test, vi } from 'vitest'

import * as api from '@/lib/api'
import { clearPriceHistoryCache, loadPriceHistory } from '@/lib/priceHistory'

const history = (t: string) => ({ ticker: t, points: [{ date: '2026-01-01', close: 1 }] })

beforeEach(() => {
  clearPriceHistoryCache()
  vi.restoreAllMocks()
})

test('12 cards, one ticker each -> 12 calls (one per distinct series)', async () => {
  const spy = vi.spyOn(api, 'getPriceHistory').mockImplementation(
    async (t: string) => history(t) as never,
  )
  const tickers = Array.from({ length: 12 }, (_, i) => `T${i}`)
  await Promise.all(tickers.map((t) => loadPriceHistory(t, 30)))
  expect(spy).toHaveBeenCalledTimes(12)
})

test('same ticker on 12 cards mounting in one tick -> ONE call', async () => {
  const spy = vi.spyOn(api, 'getPriceHistory').mockImplementation(
    async (t: string) => history(t) as never,
  )
  await Promise.all(Array.from({ length: 12 }, () => loadPriceHistory('AAPL', 30)))
  expect(spy).toHaveBeenCalledTimes(1)
})

test('remount after settle -> no refetch', async () => {
  const spy = vi.spyOn(api, 'getPriceHistory').mockImplementation(
    async (t: string) => history(t) as never,
  )
  await loadPriceHistory('AAPL', 30)
  await loadPriceHistory('AAPL', 30)
  expect(spy).toHaveBeenCalledTimes(1)
})

test('distinct spans are distinct series', async () => {
  const spy = vi.spyOn(api, 'getPriceHistory').mockImplementation(
    async (t: string) => history(t) as never,
  )
  await Promise.all([loadPriceHistory('AAPL', 30), loadPriceHistory('AAPL', 90)])
  expect(spy).toHaveBeenCalledTimes(2)
})

test('404 is a settled answer -> cached, asked once', async () => {
  const notFound = Object.assign(new Error('nf'), { status: 404 })
  const spy = vi.spyOn(api, 'getPriceHistory').mockRejectedValue(notFound)
  expect(await loadPriceHistory('NOPE', 30)).toBeNull()
  await loadPriceHistory('NOPE', 30)
  expect(spy).toHaveBeenCalledTimes(1)
})

test('a genuine failure is NOT cached -> retried, not blanked for 6h', async () => {
  const boom = Object.assign(new Error('boom'), { status: 500 })
  const spy = vi.spyOn(api, 'getPriceHistory').mockRejectedValue(boom)
  await expect(loadPriceHistory('X', 30)).rejects.toThrow()
  await expect(loadPriceHistory('X', 30)).rejects.toThrow()
  expect(spy).toHaveBeenCalledTimes(2)
})
