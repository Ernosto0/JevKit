import type { TraceEvent } from '@/lib/api';
import { ms } from '@/lib/format';

interface Props {
  events: TraceEvent[];
}

/** The execution lifecycle, one row per recorded stage. */
export function TraceTimeline({ events }: Props) {
  return (
    <div>
      {events.map((event, index) => (
        <div className="trace-row" key={`${event.stage}-${index}`}>
          <span className="trace-elapsed">{ms(event.elapsed_ms)}</span>
          <span>{event.stage}</span>
          <span className="trace-detail">
            {Object.keys(event.detail).length > 0 ? JSON.stringify(event.detail) : ''}
          </span>
        </div>
      ))}
    </div>
  );
}
