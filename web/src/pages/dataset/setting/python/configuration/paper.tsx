import {
  AutoKeywordsFormField,
  AutoQuestionsFormField,
} from '@/components/auto-keywords-form-field';
import { LayoutRecognizeFormField } from '@/components/layout-recognize-form-field';
import { MaxTokenNumberFormField } from '@/components/max-token-number-from-field';
import { SliderInputFormField } from '@/components/slider-input-form-field';
import { Button } from '@/components/ui/button';
import { useCallback } from 'react';
import { useFormContext } from 'react-hook-form';
import { FormLayout } from '@/constants/form';
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
