import type { Job } from "./api";
export type LabProps = {
  lab: number;
  catalog: any;
  job?: Job;
  busy: boolean;
  run: (body: any, lab?: number) => Promise<Job | undefined>;
};
