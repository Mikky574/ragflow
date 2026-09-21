import {
  AutoKeywordsFormField,
  AutoQuestionsFormField,
} from '@/components/auto-keywords-form-field';
import { LayoutRecognizeFormField } from '@/components/layout-recognize-form-field';
import { MaxTokenNumberFormField } from '@/components/max-token-number-from-field';
import { RAGFlowFormItem } from '@/components/ragflow-form';
import { SliderInputFormField } from '@/components/slider-input-form-field';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { FormLayout } from '@/constants/form';
import { useCallback } from 'react';
import { useFormContext } from 'react-hook-form';
import { useOwnerTenantId } from '../../../contexts/knowledge-base-context';
import {
  ConfigurationFormContainer,
  MainContainer,
} from '../configuration-form-container';
import {
  AutoMetadata,
  GlobalIndexModelItem,
  OverlappedPercent,
} from './common-item';

const PdfPaperPreset = {
  layout_recognize: 'DeepDOC',
  chunk_token_num: 550,
  delimiter: '\n',
  overlapped_percent: 0.1,
  table_context_size: 1,
  image_context_size: 0,
  image_table_context_window: 1,
  image_vision_enable: true,
  enable_children: false,
  children_delimiter: '',
};

export function PaperConfiguration() {
  const ownerTenantId = useOwnerTenantId();
  const form = useFormContext();
  const handleApplyPdfPaperPreset = useCallback(() => {
    Object.entries(PdfPaperPreset).forEach(([key, value]) =>
      form.setValue(`parser_config.${key}`, value, { shouldDirty: true }),
    );
  }, [form]);

  return (
    <MainContainer>
      <ConfigurationFormContainer>
        <div className="flex items-center justify-between gap-3 rounded-md border border-border-button p-3">
          <div className="text-sm text-text-secondary">
            {'PDF \u8bba\u6587\u9884\u8bbe\uff1a550 token\uff0c10%\u91cd\u53e0\u3002'}
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={handleApplyPdfPaperPreset}
          >
            {'\u5e94\u7528 PDF \u8bba\u6587\u9884\u8bbe'}
          </Button>
        </div>
        <LayoutRecognizeFormField ownerTenantId={ownerTenantId} />
        <MaxTokenNumberFormField initialValue={550} />
        <OverlappedPercent />
        <SliderInputFormField
          name="parser_config.table_context_size"
          label="\u8868\u683c\u4e0a\u4e0b\u6587"
          defaultValue={1}
          min={0}
          max={5}
        />
        <SliderInputFormField
          name="parser_config.image_context_size"
          label="\u56fe\u7247\u4e0a\u4e0b\u6587"
          defaultValue={0}
          min={0}
          max={5}
        />
        <RAGFlowFormItem
          name="parser_config.image_vision_enable"
          label={'\u56fe\u7247\u8bed\u4e49\u589e\u5f3a'}
          tooltip={'\u4f7f\u7528\u9ed8\u8ba4 Vision \u6a21\u578b\u63d0\u53d6\u56fe\u5185\u6587\u5b57\u548c\u56fe\u8868\u8bed\u4e49\u3002\u672a\u914d\u7f6e Vision \u6a21\u578b\u65f6\uff0c\u89e3\u6790\u4efb\u52a1\u4f1a\u660e\u786e\u63d0\u793a\u5e76\u4fdd\u7559\u539f\u56fe\u3002'}
          horizontal={true}
          labelClassName="!mb-0"
        >
          {(field) => (
            <Switch
              checked={field.value ?? true}
              onCheckedChange={field.onChange}
            />
          )}
        </RAGFlowFormItem>
        <div className="text-xs text-text-secondary">
          {'\u516c\u5f0f\u8bc6\u522b\u8bf7\u5728\u201c\u7248\u9762\u8bc6\u522b\u201d\u9009\u62e9 MinerU\uff0c\u5e76\u5f00\u542f\u5176\u201c\u516c\u5f0f\u8bc6\u522b\u201d\uff1bDeepDOC \u53ea\u4fdd\u7559\u516c\u5f0f\u56fe\u50cf\uff0c\u4e0d\u80fd\u8f6c\u4e3a LaTeX\u3002'}
        </div>
        <GlobalIndexModelItem />
      </ConfigurationFormContainer>
      <ConfigurationFormContainer>
        <AutoMetadata />
        <AutoKeywordsFormField layout={FormLayout.Horizontal} />
        <AutoQuestionsFormField layout={FormLayout.Horizontal} />
      </ConfigurationFormContainer>
    </MainContainer>
  );
}
