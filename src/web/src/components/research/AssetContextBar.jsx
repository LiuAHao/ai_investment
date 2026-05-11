/**
 * 资产上下文条组件
 */

import React from 'react';
import { TrendingUp, Globe, Building2, BarChart3 } from 'lucide-react';

const ASSET_TYPE_LABELS = {
  cn_stock: 'A股',
  us_stock: '美股',
  hk_stock: '港股',
  fund: '基金',
  etf: 'ETF',
  index: '指数',
  macro: '宏观',
  industry: '行业',
};

const ASSET_TYPE_ICONS = {
  cn_stock: TrendingUp,
  us_stock: Globe,
  hk_stock: Globe,
  fund: BarChart3,
  etf: BarChart3,
  index: BarChart3,
  macro: Building2,
  industry: Building2,
};

const AssetContextBar = ({ assets }) => {
  if (!assets || assets.length === 0) {
    return (
      <div className="text-sm text-gray-400">
        输入问题开始分析...
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 overflow-x-auto">
      <span className="text-sm text-gray-500 shrink-0">当前资产:</span>
      {assets.map((asset, index) => {
        const Icon = ASSET_TYPE_ICONS[asset.asset_type] || TrendingUp;
        const label = ASSET_TYPE_LABELS[asset.asset_type] || asset.asset_type;

        return (
          <div
            key={index}
            className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full shrink-0"
          >
            <Icon className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-medium">
              {asset.name || asset.symbol}
            </span>
            <span className="text-xs text-gray-400">
              {label}
            </span>
            {asset.confidence < 0.8 && (
              <span className="text-xs text-yellow-500" title="置信度较低">
                ?
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default AssetContextBar;
