<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="loadError" class="error">{{ loadError }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-row">
          <label class="budget-label" for="budget-slider">{{ t('restocking.budget') }}</label>
          <span class="budget-value">{{ money(budget) }}</span>
        </div>
        <input
          id="budget-slider"
          class="budget-slider"
          type="range"
          min="0"
          :max="maxBudget"
          :step="step"
          v-model.number="budget"
          @input="onSliderInput"
        />
        <div class="budget-range">
          <span>{{ money(0) }}</span>
          <span>{{ t('restocking.maxBudget') }}: {{ money(maxBudget) }}</span>
        </div>
        <div class="budget-stats">
          <div class="budget-stat">
            <div class="stat-label">{{ t('restocking.budget') }}</div>
            <div class="stat-value">{{ money(budget) }}</div>
          </div>
          <div class="budget-stat">
            <div class="stat-label">{{ t('restocking.spend') }}</div>
            <div class="stat-value">{{ money(totalCost) }}</div>
          </div>
          <div class="budget-stat">
            <div class="stat-label">{{ t('restocking.remaining') }}</div>
            <div class="stat-value">{{ money(remaining) }}</div>
          </div>
        </div>
      </div>

      <div v-if="confirmation" class="notice success-notice">{{ confirmation }}</div>
      <div v-if="submitError" class="notice error-notice">{{ submitError }}</div>
      <div v-if="refreshError" class="notice error-notice">{{ refreshError }}</div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommended') }} ({{ items.length }})</h3>
          <button class="place-order-btn" :disabled="items.length === 0 || submitting" @click="placeOrder">
            {{ submitting ? t('restocking.submitting') : t('restocking.placeOrder') }}
          </button>
        </div>
        <div v-if="items.length === 0" class="empty">{{ t('restocking.empty') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.name') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.shortfall') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.sku">
                <td>
                  <strong>{{ item.sku }}</strong>
                </td>
                <td>{{ translateProductName(item.name) }}</td>
                <td>
                  <span :class="['badge', item.trend]">{{ trendLabel(item.trend) }}</span>
                </td>
                <td class="num">{{ item.shortfall.toLocaleString() }}</td>
                <td class="num">
                  {{ item.quantity.toLocaleString() }}
                  <span v-if="item.quantity < item.shortfall" class="partial">(partial)</span>
                </td>
                <td class="num">{{ unitMoney(item.unit_cost) }}</td>
                <td class="num">
                  <strong>{{ money(item.total_cost) }}</strong>
                </td>
                <td class="num">{{ t('restocking.days', { days: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const DEBOUNCE_MS = 250

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const loadError = ref(null)
    const submitError = ref(null)
    const refreshError = ref(null)
    const confirmation = ref(null)
    const submitting = ref(false)

    const budget = ref(0)
    const maxBudget = ref(0)
    const totalCost = ref(0)
    const items = ref([])

    const remaining = computed(() => Math.max(0, budget.value - totalCost.value))
    // ~200 slider steps, rounded to a clean value, so very large budgets stay smooth
    const step = computed(() => Math.max(1, Math.round(maxBudget.value / 200)))

    const money = (amount) => formatCurrency(amount, currentCurrency.value)
    // Unit costs have cents (e.g. $18.75); whole-dollar rounding made them misleading
    const unitMoney = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)
    const trendLabel = (trend) => t(`trends.${trend}`)

    // Guards against out-of-order responses: only the latest request may update state
    let requestSeq = 0
    let debounceTimer = null

    const fetchRecommendations = async () => {
      const seq = ++requestSeq
      const data = await api.getRestockingRecommendations(budget.value)
      if (seq !== requestSeq) return false
      items.value = data.items
      totalCost.value = data.total_cost
      maxBudget.value = data.max_budget
      return true
    }

    const refresh = async () => {
      refreshError.value = null
      try {
        await fetchRecommendations()
      } catch (err) {
        refreshError.value = t('restocking.loadFailed') + err.message
      }
    }

    const onSliderInput = () => {
      confirmation.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(refresh, DEBOUNCE_MS)
    }

    const placeOrder = async () => {
      if (items.value.length === 0 || submitting.value) return
      submitting.value = true
      submitError.value = null
      confirmation.value = null
      clearTimeout(debounceTimer) // submit what is currently displayed
      try {
        const order = await api.submitRestockingOrder(items.value.map((i) => ({ sku: i.sku, quantity: i.quantity })))
        confirmation.value = t('restocking.orderPlaced', {
          id: order.id,
          days: order.lead_time_days,
        })
        await refresh()
      } catch (err) {
        const detail = err.response?.data?.detail
        submitError.value = t('restocking.submitFailed') + (typeof detail === 'string' ? detail : err.message)
      } finally {
        submitting.value = false
      }
    }

    onMounted(async () => {
      try {
        // budget=0 call is only used to discover max_budget for the slider range
        budget.value = 0
        await fetchRecommendations()
      } catch (err) {
        loadError.value = t('restocking.loadFailed') + err.message
      } finally {
        loading.value = false
      }
    })

    onBeforeUnmount(() => clearTimeout(debounceTimer))

    return {
      t,
      loading,
      loadError,
      submitError,
      refreshError,
      confirmation,
      submitting,
      budget,
      maxBudget,
      totalCost,
      items,
      remaining,
      step,
      money,
      unitMoney,
      trendLabel,
      translateProductName,
      onSliderInput,
      placeOrder,
    }
  },
}
</script>

<style scoped>
.budget-card {
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-weight: 600;
  color: #0f172a;
}

.budget-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #3b82f6;
}

.budget-range {
  display: flex;
  justify-content: space-between;
  font-size: 0.813rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.budget-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-top: 1.25rem;
}

.budget-stat {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
}

.stat-label {
  font-size: 0.813rem;
  color: #64748b;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
}

.notice {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.success-notice {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #bbf7d0;
}

.error-notice {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.place-order-btn {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1rem;
  font-weight: 500;
  cursor: pointer;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.num {
  text-align: right;
}

.partial {
  font-size: 0.75rem;
  color: #b45309;
  margin-left: 0.25rem;
}

.empty {
  padding: 1.5rem;
  color: #64748b;
  text-align: center;
}
</style>
