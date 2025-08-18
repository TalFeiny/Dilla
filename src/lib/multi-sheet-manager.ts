/**
 * Multi-Sheet Support for Spreadsheet
 * Enables multiple pages/tabs like Excel
 */

export interface Sheet {
  id: string;
  name: string;
  cells: Record<string, any>;
  isActive: boolean;
  createdAt: Date;
}

export class MultiSheetManager {
  private sheets: Map<string, Sheet> = new Map();
  private activeSheetId: string = '';
  
  constructor() {
    // Create default sheet
    this.createSheet('Sheet1');
  }
  
  /**
   * Create a new sheet
   */
  createSheet(name: string): string {
    const id = `sheet_${Date.now()}`;
    const sheet: Sheet = {
      id,
      name,
      cells: {},
      isActive: this.sheets.size === 0,
      createdAt: new Date()
    };
    
    this.sheets.set(id, sheet);
    
    if (sheet.isActive) {
      this.activeSheetId = id;
    }
    
    return id;
  }
  
  /**
   * Switch to a different sheet
   */
  switchSheet(idOrName: string): boolean {
    // Find by ID first
    if (this.sheets.has(idOrName)) {
      this.setActiveSheet(idOrName);
      return true;
    }
    
    // Find by name
    for (const [id, sheet] of this.sheets.entries()) {
      if (sheet.name === idOrName) {
        this.setActiveSheet(id);
        return true;
      }
    }
    
    return false;
  }
  
  /**
   * Get current active sheet
   */
  getActiveSheet(): Sheet | undefined {
    return this.sheets.get(this.activeSheetId);
  }
  
  /**
   * Get all sheets
   */
  getAllSheets(): Sheet[] {
    return Array.from(this.sheets.values());
  }
  
  /**
   * Delete a sheet
   */
  deleteSheet(idOrName: string): boolean {
    if (this.sheets.size <= 1) {
      console.error('Cannot delete the last sheet');
      return false;
    }
    
    let targetId = idOrName;
    
    // Find by name if not an ID
    if (!this.sheets.has(idOrName)) {
      for (const [id, sheet] of this.sheets.entries()) {
        if (sheet.name === idOrName) {
          targetId = id;
          break;
        }
      }
    }
    
    if (!this.sheets.has(targetId)) {
      return false;
    }
    
    this.sheets.delete(targetId);
    
    // If deleted sheet was active, switch to first available
    if (targetId === this.activeSheetId) {
      const firstSheet = this.sheets.values().next().value;
      if (firstSheet) {
        this.setActiveSheet(firstSheet.id);
      }
    }
    
    return true;
  }
  
  /**
   * Rename a sheet
   */
  renameSheet(idOrName: string, newName: string): boolean {
    let targetId = idOrName;
    
    // Find by name if not an ID
    if (!this.sheets.has(idOrName)) {
      for (const [id, sheet] of this.sheets.entries()) {
        if (sheet.name === idOrName) {
          targetId = id;
          break;
        }
      }
    }
    
    const sheet = this.sheets.get(targetId);
    if (!sheet) return false;
    
    sheet.name = newName;
    return true;
  }
  
  /**
   * Copy a sheet
   */
  copySheet(idOrName: string, newName?: string): string | null {
    let sourceId = idOrName;
    
    // Find by name if not an ID
    if (!this.sheets.has(idOrName)) {
      for (const [id, sheet] of this.sheets.entries()) {
        if (sheet.name === idOrName) {
          sourceId = id;
          break;
        }
      }
    }
    
    const sourceSheet = this.sheets.get(sourceId);
    if (!sourceSheet) return null;
    
    const copyName = newName || `${sourceSheet.name} (Copy)`;
    const newId = this.createSheet(copyName);
    const newSheet = this.sheets.get(newId);
    
    if (newSheet) {
      // Deep copy cells
      newSheet.cells = JSON.parse(JSON.stringify(sourceSheet.cells));
    }
    
    return newId;
  }
  
  /**
   * Reference cell from another sheet
   */
  crossSheetReference(sheetName: string, cellAddress: string): any {
    for (const sheet of this.sheets.values()) {
      if (sheet.name === sheetName) {
        return sheet.cells[cellAddress]?.value || 0;
      }
    }
    return '#REF!';
  }
  
  /**
   * 3D reference across multiple sheets (like SUM across sheets)
   */
  threeDReference(sheetRange: string, cellAddress: string, operation: 'SUM' | 'AVERAGE' | 'COUNT' = 'SUM'): any {
    const [startSheet, endSheet] = sheetRange.split(':');
    const sheets = this.getAllSheets();
    
    let inRange = false;
    const values: number[] = [];
    
    for (const sheet of sheets) {
      if (sheet.name === startSheet) inRange = true;
      
      if (inRange) {
        const value = sheet.cells[cellAddress]?.value;
        if (typeof value === 'number') {
          values.push(value);
        }
      }
      
      if (sheet.name === endSheet) break;
    }
    
    switch (operation) {
      case 'SUM':
        return values.reduce((a, b) => a + b, 0);
      case 'AVERAGE':
        return values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
      case 'COUNT':
        return values.length;
      default:
        return 0;
    }
  }
  
  private setActiveSheet(id: string) {
    // Deactivate all sheets
    this.sheets.forEach(sheet => {
      sheet.isActive = false;
    });
    
    // Activate target sheet
    const targetSheet = this.sheets.get(id);
    if (targetSheet) {
      targetSheet.isActive = true;
      this.activeSheetId = id;
    }
  }
  
  /**
   * Export all sheets data
   */
  exportData(): any {
    return {
      sheets: Array.from(this.sheets.entries()).map(([id, sheet]) => ({
        id,
        name: sheet.name,
        cells: sheet.cells,
        isActive: sheet.isActive
      })),
      activeSheetId: this.activeSheetId
    };
  }
  
  /**
   * Import sheets data
   */
  importData(data: any) {
    this.sheets.clear();
    
    if (data.sheets) {
      data.sheets.forEach((sheetData: any) => {
        const sheet: Sheet = {
          id: sheetData.id,
          name: sheetData.name,
          cells: sheetData.cells || {},
          isActive: sheetData.isActive || false,
          createdAt: new Date()
        };
        this.sheets.set(sheet.id, sheet);
      });
    }
    
    if (data.activeSheetId) {
      this.activeSheetId = data.activeSheetId;
    }
  }
}

// Export singleton instance
export const sheetManager = new MultiSheetManager();