import supabase from './supabase';
import { Company } from '../types/company';

export const companiesApi = {
  async getAll() {
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .order('created_at', { ascending: false });
    
    if (error) throw error;
    return data as Company[];
  },

  async getById(id: string) {
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .eq('id', id)
      .single();
    
    if (error) throw error;
    return data as Company;
  },

  async create(company: Omit<Company, 'id' | 'created_at' | 'updated_at'>) {
    const { data, error } = await supabase
      .from('companies')
      .insert([company])
      .select()
      .single();
    
    if (error) throw error;
    return data as Company;
  },

  async update(id: string, updates: Partial<Company>) {
    const { data, error } = await supabase
      .from('companies')
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single();
    
    if (error) throw error;
    return data as Company;
  },

  async delete(id: string) {
    const { error } = await supabase
      .from('companies')
      .delete()
      .eq('id', id);
    
    if (error) throw error;
  },

  async search(query: string) {
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .or(`name.ilike.%${query}%,sector.ilike.%${query}%`)
      .order('created_at', { ascending: false });
    
    if (error) throw error;
    return data as Company[];
  },

  async getByStatus(status: string) {
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .eq('status', status)
      .order('created_at', { ascending: false });
    
    if (error) throw error;
    return data as Company[];
  }
};