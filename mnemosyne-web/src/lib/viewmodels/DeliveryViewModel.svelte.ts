/** Delivery dashboard: portfolio scorecard + per-repo flow/forecast (spec: web-ui). */
import { ApiError } from '$lib/api/http';
import type { IntelligenceApi } from '$lib/api/mnemosyneApi';
import type {
  BacklogForecast,
  DeliveryScorecardEntry,
  FlowMetrics,
  MilestoneProgress,
  ThroughputTrend,
  WorkMix
} from '$lib/models';

export class DeliveryViewModel {
  scorecard = $state<DeliveryScorecardEntry[]>([]);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(private api: IntelligenceApi) {}

  async loadScorecard(organization?: string): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      this.scorecard = (await this.api.deliveryScorecard(organization)).scorecard;
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load delivery scorecard';
    } finally {
      this.busy = false;
    }
  }
}

/** Per-repository delivery panel on the repository detail page. */
export class RepositoryDeliveryViewModel {
  flow = $state<FlowMetrics | null>(null);
  forecast = $state<BacklogForecast | null>(null);
  throughput = $state<ThroughputTrend | null>(null);
  workMix = $state<WorkMix | null>(null);
  milestones = $state<MilestoneProgress[]>([]);
  busy = $state(false);
  error = $state<string | null>(null);

  constructor(
    private api: IntelligenceApi,
    private repoId: string
  ) {}

  async load(): Promise<void> {
    this.busy = true;
    this.error = null;
    try {
      const [flow, forecast, throughput, workMix, milestones] = await Promise.all([
        this.api.flow(this.repoId),
        this.api.forecast(this.repoId),
        this.api.throughput(this.repoId),
        this.api.workMix(this.repoId),
        this.api.milestones(this.repoId)
      ]);
      this.flow = flow;
      this.forecast = forecast;
      this.throughput = throughput;
      this.workMix = workMix;
      this.milestones = milestones.milestones;
    } catch (error) {
      this.error = error instanceof ApiError ? error.message : 'failed to load delivery metrics';
    } finally {
      this.busy = false;
    }
  }
}
