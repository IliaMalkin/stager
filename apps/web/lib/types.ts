export interface User {
  id: number;
  email: string | null;
  full_name: string | null;
  role: 'admin' | 'user';
  locale: string;
  project_quota: number | null;  // null = unlimited
}

export interface Project {
  id: number;
  name: string;
  currency: string;
  budget_minor: number | null;
  status: 'active' | 'completed' | 'archived';
  owner_user_id: number;
  created_at: string;
}

export type Category =
  | 'furniture' | 'decor' | 'textile' | 'delivery' | 'labor'
  | 'supplies' | 'photo' | 'rental' | 'transport' | 'other';

export interface Expense {
  id: number;
  project_id: number;
  amount_minor: number;
  currency: string;
  category: Category;
  description: string | null;
  paid_at: string;
  source: 'bot_photo' | 'bot_text' | 'admin_web';
  created_at: string;
}

export interface CategoryRow {
  category: Category;
  total_minor: number;
  count: number;
}

export interface DayRow {
  day: string;
  total_minor: number;
  count: number;
}

export interface ProjectSummary {
  project_id: number;
  total_minor: number;
  count: number;
  currency: string;
  by_category: CategoryRow[];
  by_day: DayRow[];
}

export const CATEGORY_LABELS_RU: Record<Category, string> = {
  furniture: 'мебель',
  decor: 'декор',
  textile: 'текстиль',
  delivery: 'доставка',
  labor: 'бригада',
  supplies: 'расходники',
  photo: 'фото',
  rental: 'аренда',
  transport: 'транспорт',
  other: 'прочее',
};
