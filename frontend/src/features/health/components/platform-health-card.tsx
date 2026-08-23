import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  DependencyState,
  PlatformHealth,
} from "@/features/health/types/platform-health";

const DEPENDENCY_LABELS = {
  operational: "Operational",
  unavailable: "Unavailable",
} as const satisfies Record<DependencyState, string>;

/**
 * Props of {@link DependencyRow}.
 */
interface DependencyRowProps {
  /** Human-readable dependency name shown in the description list. */
  readonly label: string;

  /** Normalized availability of that dependency. */
  readonly state: DependencyState;
}

/**
 * Renders one dependency and its availability as a description-list row.
 */
function DependencyRow({ label, state }: DependencyRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <dt className="text-muted-foreground">{label}</dt>

      <dd>
        <Badge variant={state === "operational" ? "secondary" : "destructive"}>
          {DEPENDENCY_LABELS[state]}
        </Badge>
      </dd>
    </div>
  );
}

/**
 * Props of {@link PlatformHealthCard}.
 */
export interface PlatformHealthCardProps {
  /** Normalized platform health, including the unreported state. */
  readonly health: PlatformHealth;
}

/**
 * Renders backend platform health, including the unavailable state.
 *
 * @remarks
 * Purely presentational and server-renderable: it reads the normalized product
 * contract and never performs data access of its own.
 */
export function PlatformHealthCard({ health }: PlatformHealthCardProps) {
  if (!health.reported) {
    return (
      <Card className="w-full max-w-md" role="status">
        <CardHeader>
          <CardTitle>Backend platform</CardTitle>
          <CardDescription>{health.reason}</CardDescription>

          <CardAction>
            <Badge variant="destructive">Unavailable</Badge>
          </CardAction>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md" role="status">
      <CardHeader>
        <CardTitle>Backend platform</CardTitle>
        <CardDescription>Version {health.version}</CardDescription>

        <CardAction>
          <Badge
            variant={health.status === "operational" ? "default" : "outline"}
          >
            {health.status === "operational" ? "Operational" : "Degraded"}
          </Badge>
        </CardAction>
      </CardHeader>

      <CardContent>
        <dl className="divide-y divide-border">
          <DependencyRow label="Database" state={health.database} />
          <DependencyRow label="Cache" state={health.cache} />
        </dl>
      </CardContent>
    </Card>
  );
}
