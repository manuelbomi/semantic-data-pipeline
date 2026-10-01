export function StatTile({ label, value, sublabel }: { label: string; value: string | number; sublabel?: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">{label}</div>
      <div className="stat-tile__value">{value}</div>
      {sublabel && <div className="stat-tile__sublabel">{sublabel}</div>}
    </div>
  );
}
