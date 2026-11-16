import { render, screen } from '@testing-library/react';
import { ResultPanel } from '@/features/monitoring/ResultPanel';
import type { CheckResult, ItemResult, Module } from '@/types';
import { PPE_ITEMS, PPE_LABELS } from '@/types';

const module: Module = {
  id: 1, factory_id: 1, name: 'Production', code: 'PRD', description: '', color: '#2B68A8', is_active: true, entry_points: [],
  ppe: Object.fromEntries(PPE_ITEMS.map((i) => [i, { required: true, min_confidence: null }])) as Module['ppe'],
};
const item = (i: (typeof PPE_ITEMS)[number], ok: boolean): ItemResult => ({ item: i, label: PPE_LABELS[i], required: true, detected: ok, confidence: ok ? 0.95 : 0.8, threshold: 0.6, status: ok ? 'pass' : 'fail', reason: ok ? '' : 'Not detected', bbox: null });

function result(passed: boolean): CheckResult {
  const items = PPE_ITEMS.map((i) => item(i, passed || i !== 'beard_net'));
  return {
    entry: { id: 9, occurred_at: '2026-11-14T08:00:00Z', passed, decision: passed ? 'granted' : 'denied', missing_items: passed ? [] : ['beard_net'], missing_labels: passed ? [] : ['Beard Net'], shift: 'A', source: 'simulation', has_evidence: false, employee: null, module: { id: 1, name: 'Production', color: '#2B68A8' }, entry_point: 'Gate A', camera: null },
    passed, decision: passed ? 'granted' : 'denied', items, missing_items: passed ? [] : ['beard_net'], missing_labels: passed ? [] : ['Beard Net'], threshold: 0.6, employee: null,
    detector: { model_name: 'simulated-detector', model_version: 'sim-1', simulated: true, notes: [] }, door: null,
    door_result: { action: passed ? 'unlocked' : 'kept_locked', simulated: true, message: passed ? 'Door released for 5 s (simulated)' : 'Access denied' }, violation_id: passed ? null : 3,
  };
}

describe('ResultPanel', () => {
  it('lists the required PPE before any check', () => {
    render(<ResultPanel result={null} module={module} door={null} />);
    expect(screen.getByTestId('result')).toHaveTextContent('Waiting for a check');
    expect(screen.getByText('Required PPE at this entry point')).toBeInTheDocument();
    PPE_ITEMS.forEach((i) => expect(screen.getByText(PPE_LABELS[i])).toBeInTheDocument());
  });

  it('shows PASS and access granted', () => {
    render(<ResultPanel result={result(true)} module={module} door={null} />);
    expect(screen.getByTestId('result')).toHaveTextContent('PASS');
    expect(screen.getByText('Access granted')).toBeInTheDocument();
    expect(screen.getByText('None — fully compliant')).toBeInTheDocument();
    expect(screen.getByText('Simulated')).toBeInTheDocument();
  });

  it('shows FAIL, the missing item and access denied', () => {
    render(<ResultPanel result={result(false)} module={module} door={null} />);
    expect(screen.getByTestId('result')).toHaveTextContent('FAIL');
    expect(screen.getByTestId('result')).toHaveTextContent('1 required item missing');
    expect(screen.getByText('Missing PPE (1)')).toBeInTheDocument();
    expect(screen.getByText('Detected PPE (4)')).toBeInTheDocument();
    expect(screen.getAllByText('Access denied').length).toBeGreaterThan(0);
  });
});
