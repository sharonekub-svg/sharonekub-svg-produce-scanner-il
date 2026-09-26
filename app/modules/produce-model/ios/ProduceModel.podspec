Pod::Spec.new do |s|
  s.name           = 'ProduceModel'
  s.version        = '1.0.0'
  s.summary        = 'On-device Core ML produce scanner model'
  s.author         = ''
  s.homepage       = 'https://example.invalid'
  s.license        = 'UNLICENSED'
  s.platforms      = { :ios => '16.0' }
  s.source         = { git: '' }
  s.static_framework = true
  s.dependency 'ExpoModulesCore'
  s.source_files   = '**/*.swift'
  # The exported ProduceScanner.mlpackage is copied here by scripts/sync_model_to_app.sh and shipped
  # raw; it is compiled once on device (MLModel.compileModel) and cached in Application Support.
  s.resource_bundles = { 'ProduceModelAssets' => ['../models/**/*'] }
end
