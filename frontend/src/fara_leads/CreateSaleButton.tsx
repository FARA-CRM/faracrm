/**
 * Кнопка «Создать продажу» в тулбаре формы лида — ручной путь той же
 * механики, что автосоздание по стадии-триггеру (POST /leads/{id}/create_sale).
 * Нужна для повторных заказов: у одного лида (клиента) много продаж.
 *
 * Воронок продаж может быть несколько (issue #50), поэтому при двух и более
 * активных воронках кнопка открывает меню «в какую воронку»; заказ получает
 * первую стадию выбранной воронки.
 *
 * Тулбар формы не рендерит actions в режиме создания, поэтому id из маршрута
 * здесь всегда есть. После создания переходим в новую продажу.
 */

import { Button, Menu } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconShoppingCartPlus } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { useSearchQuery } from '@/services/api/crudApi';
import { useCreateSaleFromLeadMutation } from './leadsApi';

export function CreateSaleButton() {
  const { t } = useTranslation('leads');
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [createSale, { isLoading }] = useCreateSaleFromLeadMutation();
  const { data } = useSearchQuery({
    model: 'sale_funnel',
    fields: ['id', 'name'],
    limit: 100,
    sort: 'sequence',
    order: 'asc',
    filter: [['active', '=', true]],
  });
  const funnels = data?.data ?? [];

  const handleCreate = async (funnelId?: number) => {
    try {
      const { sale_id } = await createSale({
        leadId: Number(id),
        funnelId,
      }).unwrap();
      navigate(`/sales/${sale_id}`);
    } catch {
      notifications.show({
        color: 'red',
        message: t('sale_link.create_failed'),
      });
    }
  };

  const label = t('sale_link.create_sale');

  // Одна воронка (или пока ни одной) — меню не нужно, сразу создаём.
  if (funnels.length < 2) {
    return (
      <Button
        variant="light"
        leftSection={<IconShoppingCartPlus size={16} />}
        onClick={() => handleCreate(funnels[0] && Number(funnels[0].id))}
        loading={isLoading}>
        {label}
      </Button>
    );
  }

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button
          variant="light"
          leftSection={<IconShoppingCartPlus size={16} />}
          loading={isLoading}>
          {label}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{t('sale_link.choose_funnel')}</Menu.Label>
        {funnels.map(funnel => (
          <Menu.Item
            key={funnel.id}
            onClick={() => handleCreate(Number(funnel.id))}>
            {String(funnel.name ?? funnel.id)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
