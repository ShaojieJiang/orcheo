import type { TraceRecord, TraceSpan } from "@evilmartians/agent-prism-types";

import {
  filterSpansRecursively,
  flattenSpans,
} from "@evilmartians/agent-prism-data";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { DetailsViewProps } from "../DetailsView/DetailsView";
import { type BadgeProps } from "../Badge";
import { useIsMobile } from "../shared";
import { type SpanCardViewOptions } from "../SpanCard/SpanCard";
import { TraceViewerDesktopLayout } from "./TraceViewerDesktopLayout";
import { TraceViewerMobileLayout } from "./TraceViewerMobileLayout";

export interface TraceViewerData {
  traceRecord: TraceRecord;
  badges?: Array<BadgeProps>;
  spans: TraceSpan[];
  spanCardViewOptions?: SpanCardViewOptions;
}

export interface TraceViewerProps {
  data: Array<TraceViewerData>;
  spanCardViewOptions?: SpanCardViewOptions;
  detailsViewProps?: Partial<DetailsViewProps>;
  activeTraceId?: string;
}

export const TraceViewer = ({
  data,
  spanCardViewOptions,
  detailsViewProps,
  activeTraceId,
}: TraceViewerProps) => {
  const isMobile = useIsMobile();
  const hasInitialized = React.useRef(false);

  const initialTraceData = useMemo(() => {
    if (activeTraceId) {
      const activeTrace = data.find(
        (item) => item.traceRecord.id === activeTraceId,
      );
      if (activeTrace) {
        return activeTrace;
      }
    }
    return data[0];
  }, [activeTraceId, data]);

  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | undefined>();
  const [searchValue, setSearchValue] = useState("");
  const [traceListExpanded, setTraceListExpanded] = useState(true);

  const [selectedTrace, setSelectedTrace] = useState<
    TraceRecordWithDisplayData | undefined
  >(
    initialTraceData
      ? {
          ...initialTraceData.traceRecord,
          badges: initialTraceData.badges,
          spanCardViewOptions: initialTraceData.spanCardViewOptions,
        }
      : undefined,
  );
  const [selectedTraceSpans, setSelectedTraceSpans] = useState<TraceSpan[]>(
    initialTraceData?.spans ?? [],
  );
  const [selectedTraceId, setSelectedTraceId] = useState<string | undefined>(
    initialTraceData?.traceRecord.id,
  );
  const [hasUserSelection, setHasUserSelection] = useState(false);
  const previousTraceIdRef = useRef<string | undefined>(
    initialTraceData?.traceRecord.id,
  );

  const traceRecords: TraceRecordWithDisplayData[] = useMemo(() => {
    return data.map((item) => ({
      ...item.traceRecord,
      badges: item.badges,
      spanCardViewOptions: item.spanCardViewOptions,
    }));
  }, [data]);

  const filteredSpans = useMemo(() => {
    if (!searchValue.trim()) {
      return selectedTraceSpans;
    }
    return filterSpansRecursively(selectedTraceSpans, searchValue);
  }, [selectedTraceSpans, searchValue]);

  const allIds = useMemo(() => {
    return flattenSpans(selectedTraceSpans).map((span) => span.id);
  }, [selectedTraceSpans]);

  const [expandedSpansIds, setExpandedSpansIds] = useState<string[]>(allIds);

  useEffect(() => {
    setExpandedSpansIds(allIds);
  }, [allIds]);

  useEffect(() => {
    if (!activeTraceId) {
      return;
    }

    const hasActiveTrace = data.some(
      (item) => item.traceRecord.id === activeTraceId,
    );

    if (hasActiveTrace && activeTraceId !== selectedTraceId) {
      setHasUserSelection(false);
      setSelectedTraceId(activeTraceId);
    }
  }, [activeTraceId, data, selectedTraceId]);

  useEffect(() => {
    if (data.length === 0) {
      setSelectedTrace(undefined);
      setSelectedTraceSpans([]);
      setSelectedTraceId(undefined);
      setHasUserSelection(false);
      if (previousTraceIdRef.current) {
        previousTraceIdRef.current = undefined;
        setSelectedSpan(undefined);
        setExpandedSpansIds([]);
      }
      return;
    }

    if (!selectedTraceId) {
      if (!hasUserSelection) {
        const firstTrace = data[0];
        if (firstTrace) {
          setSelectedTraceId(firstTrace.traceRecord.id);
        }
        return;
      }
      setSelectedTrace(undefined);
      setSelectedTraceSpans([]);
      if (previousTraceIdRef.current) {
        previousTraceIdRef.current = undefined;
        setSelectedSpan(undefined);
        setExpandedSpansIds([]);
      }
      return;
    }

    const traceData = data.find(
      (item) => item.traceRecord.id === selectedTraceId,
    );

    if (!traceData) {
      const fallback = data[0];
      if (fallback && fallback.traceRecord.id !== selectedTraceId) {
        setSelectedTraceId(fallback.traceRecord.id);
      } else {
        setSelectedTrace(undefined);
        setSelectedTraceSpans([]);
        setHasUserSelection(false);
        if (previousTraceIdRef.current) {
          previousTraceIdRef.current = undefined;
          setSelectedSpan(undefined);
          setExpandedSpansIds([]);
        }
      }
      return;
    }

    const nextTrace: TraceRecordWithDisplayData = {
      ...traceData.traceRecord,
      badges: traceData.badges,
      spanCardViewOptions: traceData.spanCardViewOptions,
    };

    setSelectedTrace((prev) => {
      if (
        prev &&
        prev.id === nextTrace.id &&
        prev.badges === nextTrace.badges &&
        prev.spanCardViewOptions === nextTrace.spanCardViewOptions
      ) {
        return prev;
      }
      return nextTrace;
    });

    setSelectedTraceSpans((prev) =>
      prev === traceData.spans ? prev : traceData.spans,
    );

    if (previousTraceIdRef.current !== traceData.traceRecord.id) {
      previousTraceIdRef.current = traceData.traceRecord.id;
      setSelectedSpan(undefined);
      setExpandedSpansIds([]);
    }
  }, [data, selectedTraceId, hasUserSelection]);

  useEffect(() => {
    if (!hasInitialized.current) {
      hasInitialized.current = true;
    }

    if (!isMobile && selectedTraceSpans.length > 0 && !selectedSpan) {
      setSelectedSpan(selectedTraceSpans[0]);
    }
  }, [selectedTraceSpans, isMobile, selectedSpan]);

  const handleExpandAll = useCallback(() => {
    setExpandedSpansIds(allIds);
  }, [allIds]);

  const handleCollapseAll = useCallback(() => {
    setExpandedSpansIds([]);
  }, []);

  const handleTraceSelect = useCallback((trace: TraceRecord) => {
    setHasUserSelection(true);
    setSelectedTraceId(trace.id);
  }, []);

  const handleClearTraceSelection = useCallback(() => {
    previousTraceIdRef.current = undefined;
    setHasUserSelection(true);
    setSelectedTrace(undefined);
    setSelectedTraceSpans([]);
    setSelectedSpan(undefined);
    setExpandedSpansIds([]);
    setSelectedTraceId(undefined);
  }, []);

  const props: TraceViewerLayoutProps = {
    traceRecords,
    traceListExpanded,
    setTraceListExpanded,
    selectedTrace,
    selectedTraceId: selectedTraceId,
    selectedSpan,
    setSelectedSpan,
    searchValue,
    setSearchValue,
    filteredSpans,
    expandedSpansIds,
    setExpandedSpansIds,
    handleExpandAll,
    handleCollapseAll,
    handleTraceSelect,
    spanCardViewOptions:
      spanCardViewOptions || selectedTrace?.spanCardViewOptions,
    onClearTraceSelection: handleClearTraceSelection,
    detailsViewProps,
  };

  return (
    <div className="h-[calc(100vh-50px)]">
      <div className="hidden h-full lg:block">
        <TraceViewerDesktopLayout {...props} />
      </div>
      <div className="h-full lg:hidden">
        <TraceViewerMobileLayout {...props} />
      </div>
    </div>
  );
};

export interface TraceRecordWithDisplayData extends TraceRecord {
  spanCardViewOptions?: SpanCardViewOptions;
  badges?: BadgeProps[];
}

export interface TraceViewerLayoutProps {
  traceRecords: TraceRecordWithDisplayData[];
  traceListExpanded: boolean;
  setTraceListExpanded: (expanded: boolean) => void;
  selectedTrace: TraceRecordWithDisplayData | undefined;
  selectedTraceId?: string;
  selectedSpan: TraceSpan | undefined;
  setSelectedSpan: (span: TraceSpan | undefined) => void;
  searchValue: string;
  setSearchValue: (value: string) => void;
  filteredSpans: TraceSpan[];
  expandedSpansIds: string[];
  setExpandedSpansIds: (ids: string[]) => void;
  handleExpandAll: () => void;
  handleCollapseAll: () => void;
  handleTraceSelect: (trace: TraceRecord) => void;
  spanCardViewOptions?: SpanCardViewOptions;
  onClearTraceSelection: () => void;
  detailsViewProps?: Partial<DetailsViewProps>;
}
