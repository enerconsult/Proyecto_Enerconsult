import React, { useState, useEffect } from 'react';
import { Save, Play, FileSpreadsheet, Folder, Database, Calendar, FileText, Filter } from 'lucide-react';

interface ConfigTabProps {
  addLog: (message: string) => void;
}

export default function ConfigTab({ addLog }: ConfigTabProps) {
  const [config, setConfig] = useState({
    usuario: '',
    password: '',
    rutaLocal: '/datos/xm',
    fechaInicio: '2025-01-01',
    fechaFin: '2025-01-31',
  });

  const [dbStats, setDbStats] = useState({
    exists: false,
    size: '0 MB',
    lastUpdate: '--',
  });

  const [counts, setCounts] = useState({
    files: 12,
    filters: 8,
  });

  useEffect(() => {
    // Simular carga de stats
    setTimeout(() => {
      setDbStats({
        exists: true,
        size: '156.42 MB',
        lastUpdate: '2025-01-10 09:45',
      });
    }, 500);
  }, []);

  const handleSave = () => {
    addLog('Configuración guardada exitosamente');
  };

  const handleDownload = () => {
    addLog('🚀 INICIANDO DESCARGA DE ARCHIVOS...');
    setTimeout(() => addLog('⬇️ Descargando archivos desde XM FTP...'), 1000);
    setTimeout(() => addLog('💾 Procesando base de datos...'), 2500);
    setTimeout(() => addLog('✅ Proceso completado: 124 archivos procesados'), 4000);
  };

  const handleReport = () => {
    addLog('📈 Generando reporte horizontal...');
    setTimeout(() => addLog('✅ Reporte Excel generado: Reporte_Horizontal_XM.xlsx'), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Credentials Section */}
      <section className="border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Database size={20} className="text-[#0093d0]" />
          Credenciales FTP y Rutas
        </h3>
        
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Usuario FTP
            </label>
            <input
              type="text"
              value={config.usuario}
              onChange={(e) => setConfig({ ...config, usuario: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0093d0] focus:border-transparent"
              placeholder="usuario@xm.com.co"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password FTP
            </label>
            <input
              type="password"
              value={config.password}
              onChange={(e) => setConfig({ ...config, password: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0093d0] focus:border-transparent"
              placeholder="••••••••"
            />
          </div>
          
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Ruta Local
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={config.rutaLocal}
                onChange={(e) => setConfig({ ...config, rutaLocal: e.target.value })}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0093d0] focus:border-transparent"
              />
              <button className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">
                <Folder size={20} />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Date Range Section */}
      <section className="border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Calendar size={20} className="text-[#0093d0]" />
          Rango de Fechas (YYYY-MM-DD)
        </h3>
        
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fecha Inicio
            </label>
            <input
              type="date"
              value={config.fechaInicio}
              onChange={(e) => setConfig({ ...config, fechaInicio: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0093d0] focus:border-transparent"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Fecha Fin
            </label>
            <input
              type="date"
              value={config.fechaFin}
              onChange={(e) => setConfig({ ...config, fechaFin: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#0093d0] focus:border-transparent"
            />
          </div>
        </div>
      </section>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-6 py-3 bg-[#8cc63f] hover:bg-[#7ab828] text-white rounded-lg transition-colors"
        >
          <Save size={20} />
          Guardar Config
        </button>
        
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-6 py-3 bg-[#0093d0] hover:bg-[#007bb5] text-white rounded-lg transition-colors"
        >
          <Play size={20} />
          EJECUTAR DESCARGA + BD
        </button>
        
        <button
          onClick={handleReport}
          className="flex items-center gap-2 px-6 py-3 bg-[#0093d0] hover:bg-[#007bb5] text-white rounded-lg transition-colors"
        >
          <FileSpreadsheet size={20} />
          GENERAR REPORTE
        </button>
      </div>

      {/* Dashboard Section */}
      <div className="grid grid-cols-2 gap-6 mt-8">
        {/* System Status */}
        <section className="border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Estado del Sistema</h3>
          
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Database size={18} className={dbStats.exists ? 'text-green-500' : 'text-red-500'} />
              <div>
                <p className="text-sm font-medium text-gray-700">Base de Datos</p>
                <p className={`text-sm ${dbStats.exists ? 'text-green-600' : 'text-red-600'}`}>
                  {dbStats.exists ? dbStats.size : 'No encontrada'}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Calendar size={18} className="text-gray-500" />
              <div>
                <p className="text-sm font-medium text-gray-700">Última Modificación</p>
                <p className="text-sm text-gray-600">{dbStats.lastUpdate}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-gray-500" />
              <div>
                <p className="text-sm font-medium text-gray-700">Archivos Configurados</p>
                <p className="text-sm text-gray-600">{counts.files}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Filter size={18} className="text-gray-500" />
              <div>
                <p className="text-sm font-medium text-gray-700">Filtros Reporte</p>
                <p className="text-sm text-gray-600">{counts.filters}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Workflow */}
        <section className="border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Flujo de Trabajo</h3>
          
          <div className="text-center py-4">
            <div className="text-2xl font-bold text-[#0093d0] mb-6">
              ☁️ XM → ⬇️ Descarga ��� 💾 BD → 📈 Visualizador
            </div>
            
            <div className="text-left space-y-2 text-sm text-gray-600">
              <p>1. Configura tus credenciales y rutas.</p>
              <p>2. Ejecuta 'Descarga + BD' para actualizar datos.</p>
              <p>3. Usa el Visualizador o Genera Reportes Excel.</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
