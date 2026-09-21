import { Route, Routes } from 'react-router-dom';
import { Shell } from '@/components/Shell';
import { Overview } from '@/pages/Overview';
import { Tasks } from '@/pages/Tasks';
import { Playground } from '@/pages/Playground';
import { Traces } from '@/pages/Traces';
import { Benchmarks } from '@/pages/Benchmarks';
import { Policies } from '@/pages/Policies';
import { Settings } from '@/pages/Settings';

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Overview />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="playground" element={<Playground />} />
        <Route path="traces" element={<Traces />} />
        <Route path="benchmarks" element={<Benchmarks />} />
        <Route path="policies" element={<Policies />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<div className="empty">Page not found.</div>} />
      </Route>
    </Routes>
  );
}
