/**
 * Leads API — дополнительные endpoints модуля leads (injectEndpoints в общий
 * crudApi, как fara_cron/cronApi.ts).
 */

import { crudApi } from '@services/api/crudApi';

export interface CreateSaleFromLeadArgs {
  leadId: number;
  /** Воронка продаж, в которую создать заказ; без неё — воронка по умолчанию. */
  funnelId?: number;
}

const injectedRtkApi = crudApi.injectEndpoints({
  endpoints: build => ({
    /** Создать продажу из лида → { sale_id }. Бэкенд: Lead.create_sale. */
    createSaleFromLead: build.mutation<
      CreateSaleFromLeadResponse,
      CreateSaleFromLeadArgs
    >({
      query: ({ leadId, funnelId }) => ({
        url: `/leads/${leadId}/create_sale`,
        method: 'POST',
        params: funnelId ? { funnel_id: funnelId } : undefined,
      }),
      // Новая продажа должна появиться в списке продаж и во вкладке
      // «Продажи» лида: обе выборки — useSearchQuery по sales (тег LIST).
      invalidatesTags: [{ type: 'sales', id: 'LIST' }],
    }),
  }),
  overrideExisting: false,
});

export type CreateSaleFromLeadResponse = {
  sale_id: number;
};

export const { useCreateSaleFromLeadMutation } = injectedRtkApi;
